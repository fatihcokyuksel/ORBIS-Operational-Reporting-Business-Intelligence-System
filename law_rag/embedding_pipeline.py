from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from law_rag.chroma_manager import add_embeddings, get_collection
from law_rag.config import RagSettings
from law_rag.duplicate_checker import filter_duplicate_chunks
from law_rag.metadata import build_standard_metadata
from rag_preprocess.models import Chunk

logger = logging.getLogger(__name__)


def _as_list_embeddings(raw_embeddings: Any) -> list[list[float]]:
    if hasattr(raw_embeddings, "tolist"):
        return raw_embeddings.tolist()
    return [embedding.tolist() if hasattr(embedding, "tolist") else list(embedding) for embedding in raw_embeddings]


def _batched(items: list[Chunk], batch_size: int) -> list[list[Chunk]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def standardize_chunks(
    chunks: list[Chunk],
    settings: RagSettings,
) -> list[Chunk]:
    standardized: list[Chunk] = []
    for chunk in chunks:
        updated_metadata = build_standard_metadata(
            dict(chunk.metadata),
            chunk.text,
            embedding_model_name=settings.embedding_model_name,
            language=settings.language,
            aliases=settings.law_aliases,
        )
        standardized.append(replace(chunk, metadata=updated_metadata))
    return standardized


def ingest_chunks_into_chroma(
    chunks: list[Chunk],
    *,
    settings: RagSettings,
    embedding_model: Any,
) -> dict[str, int | str]:
    collection = get_collection(settings)
    standardized_chunks = standardize_chunks(chunks, settings)
    duplicate_result = filter_duplicate_chunks(
        collection,
        standardized_chunks,
        batch_size=settings.chroma_add_batch_size,
    )
    new_chunks = duplicate_result.new_chunks
    if not new_chunks:
        return {
            "collection_name": settings.chroma_collection_name,
            "db_path": str(settings.chroma_db_path),
            "input_chunk_count": len(chunks),
            "added_chunk_count": 0,
            "skipped_duplicate_ids": duplicate_result.skipped_by_id,
            "skipped_duplicate_hashes": duplicate_result.skipped_by_hash,
        }

    saved_count = 0
    for batch in _batched(new_chunks, settings.chroma_add_batch_size):
        texts = [chunk.text for chunk in batch]
        encoded = embedding_model.encode(
            texts,
            batch_size=settings.embedding_batch_size,
            max_length=settings.max_model_tokens,
        )
        embeddings = _as_list_embeddings(encoded["dense_vecs"])
        saved_count += add_embeddings(
            collection,
            ids=[chunk.id for chunk in batch],
            documents=texts,
            metadatas=[chunk.metadata for chunk in batch],
            embeddings=embeddings,
        )
        logger.info("Chroma add ilerleme: %d/%d", saved_count, len(new_chunks))

    return {
        "collection_name": settings.chroma_collection_name,
        "db_path": str(settings.chroma_db_path),
        "input_chunk_count": len(chunks),
        "added_chunk_count": saved_count,
        "skipped_duplicate_ids": duplicate_result.skipped_by_id,
        "skipped_duplicate_hashes": duplicate_result.skipped_by_hash,
    }
