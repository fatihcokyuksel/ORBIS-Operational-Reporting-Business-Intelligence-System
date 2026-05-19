import os
from pathlib import Path
from typing import Any

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from dotenv import load_dotenv
from fastapi import APIRouter
from google import genai
from google.genai import types
from pydantic import BaseModel

from law_rag.chroma_manager import get_collection, load_embedding_model
from law_rag.config import get_rag_settings
from law_rag.query_parser import parse_law_article_query
from law_rag.retrieval import retrieve_law_article


load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAG_SETTINGS = get_rag_settings(PROJECT_ROOT)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

models: dict[str, Any] = {}
router = APIRouter()
genai_client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
collection = get_collection(RAG_SETTINGS)


class FileData(BaseModel):
    name: str
    type: str
    data: str


class Query(BaseModel):
    question: str
    file: FileData | None = None


def init_bge_model():
    print("Loading BGE-M3 model, please wait...")
    models["bge"] = load_embedding_model(RAG_SETTINGS.embedding_model_name)
    print("RAG service is ready.")


def clear_bge_model():
    models.clear()


def _encode_query(question: str) -> list[float]:
    query_embedding = models["bge"].encode(
        [question],
        batch_size=1,
        max_length=RAG_SETTINGS.max_model_tokens,
    )["dense_vecs"][0]
    return query_embedding.tolist() if hasattr(query_embedding, "tolist") else list(query_embedding)


def _source_name(meta: dict[str, Any]) -> str:
    source_file = str(meta.get("source_file") or meta.get("source") or meta.get("document_name") or "").strip()
    kanun_adi = str(meta.get("kanun_adi") or meta.get("law_name") or meta.get("official_name") or "").strip()
    kanun_no = str(meta.get("kanun_no") or meta.get("law_no") or "").strip()

    if kanun_no and kanun_adi:
        return f"{kanun_no} sayili {kanun_adi}"
    if kanun_adi:
        return kanun_adi
    if source_file:
        return source_file
    return "Bilinmeyen kaynak"


def _page_value(meta: dict[str, Any]) -> Any:
    return meta.get("page") or meta.get("page_start") or meta.get("sayfa") or ""


def _build_context(results: dict[str, Any]) -> str:
    context_list = []
    documents = (results.get("documents") or [[]])[0]
    metadatas = (results.get("metadatas") or [[]])[0]
    for doc, meta in zip(documents, metadatas):
        source_name = _source_name(meta)
        page_value = _page_value(meta)
        context_list.append(
            f"KAYNAK: {source_name} | SAYFA: {page_value}\nICERIK: {doc}"
        )
    return "\n\n---\n\n".join(context_list)


def semantic_search(question: str, *, law_filter: dict[str, str] | None = None, top_k: int = 7) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "query_embeddings": [_encode_query(question)],
        "n_results": top_k,
        "include": ["documents", "metadatas"],
    }
    if law_filter:
        kwargs["where"] = law_filter
    return collection.query(**kwargs)


def _build_article_answer(parsed_query, article_result: dict[str, Any]) -> str:
    rows = article_result["rows"]
    if not rows:
        return ""

    first_meta = rows[0]["metadata"]
    source_name = _source_name(first_meta)
    article_no = str(first_meta.get("madde_no") or first_meta.get("article_no") or parsed_query.article_no)
    body = article_result["combined_text"].strip()
    return f"{source_name} Madde {article_no}\n\n{body}".strip()


def _law_filter_from_query(parsed_query) -> dict[str, str] | None:
    if parsed_query.law_no:
        return {"kanun_no": parsed_query.law_no}
    if parsed_query.normalized_law_name:
        return {"kanun_adi_normalized": parsed_query.normalized_law_name}
    return None


def answer_with_llm(question: str, results: dict[str, Any], file: FileData | None = None) -> str:
    context = _build_context(results)

    system_instruction = """Sen uzman bir muhasebe ve finans danismanisin. Sana referans olmasi icin arka planda mevzuat baglam bilgileri saglanmaktadir.

COK ONEMLI KURALLAR:
1. Kullanicinin sorusu gunluk bir selamlama veya muhasebe disi genel bir sohbet ise, baglam bilgilerini tamamen yok say ve normal bir insan gibi asla kaynak belirtmeden cevap ver.
2. Sadece kullanicinin sorusu sana verilen baglam bilgileriyle dogrudan alakaliysa o baglami kullan.
3. Baglam bilgilerinden yararlanarak yanit uretiyorsan, yalnizca yanitinda gercekten kullandigin maddelerin kaynagini belirt. Kullanmadigin kaynaklari listeleme.
4. Kendi genel bilginle cevap veriyorsan veya baglami kullanmadiysan asla kaynak, kanun veya sayfa uydurma ya da belirtme."""

    prompt = f"""BAGLAM BILGILERI (SADECE SORUYLA ILGILIYSE KULLAN, DEGILSE YOK SAY):
{context}

Kullanicinin Sorusu: {question}"""

    contents_list: list[Any] = [prompt]
    if file:
        import base64

        raw_data = file.data
        if "," in raw_data:
            raw_data = raw_data.split(",")[1]

        file_bytes = base64.b64decode(raw_data)
        contents_list.append(
            types.Part.from_bytes(
                data=file_bytes,
                mime_type=file.type,
            )
        )

    response = genai_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents_list,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction
        ),
    )
    return response.text or ""


@router.get("/health/rag")
async def health():
    return {
        "status": "ok",
        "chroma_db_path": str(RAG_SETTINGS.chroma_db_path),
        "collection": RAG_SETTINGS.chroma_collection_name,
        "documents": collection.count(),
    }


@router.post("/ask")
async def ask_question(query: Query):
    parsed_query = parse_law_article_query(query.question, RAG_SETTINGS.law_aliases)
    if parsed_query:
        article_result = retrieve_law_article(collection, parsed_query)
        if article_result["rows"]:
            return {
                "answer": _build_article_answer(parsed_query, article_result),
                "sources": [row["metadata"] for row in article_result["rows"]],
                "retrieval_mode": article_result["strategy"],
            }

        filtered_results = semantic_search(
            query.question,
            law_filter=_law_filter_from_query(parsed_query),
            top_k=5,
        )
        if (filtered_results.get("documents") or [[]])[0]:
            answer_text = answer_with_llm(query.question, filtered_results, query.file)
            return {
                "answer": answer_text,
                "sources": filtered_results["metadatas"][0],
                "retrieval_mode": "semantic_fallback",
            }

    results = semantic_search(query.question, top_k=7)
    answer_text = answer_with_llm(query.question, results, query.file)
    lowered_answer = answer_text.lower()

    not_found_markers = (
        "ulasamadim",
        "bulamadim",
        "veritabaninda",
    )

    if any(marker in lowered_answer for marker in not_found_markers):
        return {
            "answer": "Veritabaninda bu konuya iliskin bir sonuc bulamadim. Lutfen daha detayli bilgi girer misiniz?",
            "sources": [],
            "retrieval_mode": "semantic",
        }

    return {
        "answer": answer_text,
        "sources": results["metadatas"][0],
        "retrieval_mode": "semantic",
    }
