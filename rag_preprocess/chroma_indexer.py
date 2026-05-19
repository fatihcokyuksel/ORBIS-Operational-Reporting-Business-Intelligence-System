from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from law_rag.chroma_manager import get_collection as shared_get_collection
from law_rag.chroma_manager import load_embedding_model as shared_load_embedding_model
from law_rag.config import get_rag_settings
from law_rag.embedding_pipeline import ingest_chunks_into_chroma
from rag_preprocess.models import Chunk

logger = logging.getLogger(__name__)


def load_embedding_model() -> Any:
    settings = get_rag_settings(Path(__file__).resolve().parents[1])
    return shared_load_embedding_model(settings.embedding_model_name)


def get_chroma_collection(chroma_db_path: Path, collection_name: str) -> Any:
    settings = get_rag_settings(Path(__file__).resolve().parents[1])
    settings.chroma_db_path = chroma_db_path
    settings.chroma_collection_name = collection_name
    return shared_get_collection(settings)


def save_to_chromadb(
    chunks: list[Chunk],
    chroma_db_path: Path,
    collection_name: str,
    embedding_model: Any,
) -> Any:
    settings = get_rag_settings(Path(__file__).resolve().parents[1])
    settings.chroma_db_path = chroma_db_path
    settings.chroma_collection_name = collection_name
    collection = shared_get_collection(settings)
    if not chunks:
        logger.warning("ChromaDB kaydi icin chunk bulunamadi.")
        return collection

    summary = ingest_chunks_into_chroma(
        chunks,
        settings=settings,
        embedding_model=embedding_model,
    )
    logger.info("ChromaDB append tamamlandi: %s", summary)
    return collection
