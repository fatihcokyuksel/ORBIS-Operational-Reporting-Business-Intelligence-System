from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from law_rag.config import RagSettings
from law_rag.metadata import sanitize_metadata_for_chroma

logger = logging.getLogger(__name__)


def load_embedding_model(model_name: str) -> Any:
    try:
        from FlagEmbedding import BGEM3FlagModel  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "FlagEmbedding kurulu degil. `pip install FlagEmbedding` komutuyla kurun."
        ) from exc

    logger.info("Embedding modeli yukleniyor: %s", model_name)
    return BGEM3FlagModel(model_name, use_fp16=True)


def get_persistent_client(chroma_db_path: Path) -> Any:
    try:
        import chromadb  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "ChromaDB kurulu degil. `pip install chromadb` komutuyla kurun."
        ) from exc

    chroma_db_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_db_path))


def get_collection(settings: RagSettings) -> Any:
    client = get_persistent_client(settings.chroma_db_path)
    return client.get_or_create_collection(name=settings.chroma_collection_name)


def add_embeddings(
    collection: Any,
    *,
    ids: list[str],
    documents: list[str],
    metadatas: list[dict[str, Any]],
    embeddings: list[list[float]],
) -> int:
    if not ids:
        return 0
    collection.add(
        ids=ids,
        documents=documents,
        metadatas=[sanitize_metadata_for_chroma(metadata) for metadata in metadatas],
        embeddings=embeddings,
    )
    return len(ids)
