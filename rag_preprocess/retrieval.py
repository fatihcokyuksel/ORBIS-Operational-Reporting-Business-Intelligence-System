from __future__ import annotations

from typing import Any

from rag_preprocess.config import MAX_MODEL_TOKENS


def _hits_from_chroma_get(result: dict[str, Any]) -> list[dict[str, Any]]:
    ids = result.get("ids") or []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    hits: list[dict[str, Any]] = []
    for index, item_id in enumerate(ids):
        hits.append(
            {
                "id": item_id,
                "text": documents[index] if index < len(documents) else "",
                "metadata": metadatas[index] if index < len(metadatas) else {},
            }
        )
    return hits


def _sort_article_hits(hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        hits,
        key=lambda hit: (
            int(hit["metadata"].get("chunk_index") or 0),
            int(hit["metadata"].get("article_part") or 0),
        ),
    )


def lookup_article(collection: Any, law_no: str, article_no: str) -> dict[str, Any]:
    where = {"$and": [{"law_no": law_no}, {"article_no": article_no}]}
    result = collection.get(where=where, include=["documents", "metadatas"])
    hits = _hits_from_chroma_get(result)

    if not hits:
        law_result = collection.get(
            where={"law_no": law_no},
            include=["documents", "metadatas"],
        )
        padded = f"|{article_no}|"
        hits = [
            hit
            for hit in _hits_from_chroma_get(law_result)
            if padded in str(hit["metadata"].get("included_articles_padded") or "")
        ]

    hits = _sort_article_hits(hits)
    combined_text = "\n\n".join(hit["text"] for hit in hits if hit.get("text"))
    return {
        "law_no": law_no,
        "article_no": article_no,
        "count": len(hits),
        "hits": hits,
        "combined_text": combined_text,
    }


def semantic_search(
    collection: Any,
    embedding_model: Any,
    query: str,
    law_no: str | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    encoded = embedding_model.encode([query], max_length=MAX_MODEL_TOKENS)
    query_embedding = encoded["dense_vecs"][0]
    if hasattr(query_embedding, "tolist"):
        query_embedding = query_embedding.tolist()

    kwargs: dict[str, Any] = {
        "query_embeddings": [query_embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if law_no:
        kwargs["where"] = {"law_no": law_no}
    return collection.query(**kwargs)
