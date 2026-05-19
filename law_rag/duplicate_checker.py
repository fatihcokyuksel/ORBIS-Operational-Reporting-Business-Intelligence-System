from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rag_preprocess.models import Chunk


@dataclass(slots=True)
class DuplicateCheckResult:
    new_chunks: list[Chunk]
    skipped_by_id: int
    skipped_by_hash: int


def _batched(items: list[Any], batch_size: int) -> list[list[Any]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def _content_hash_exists(collection: Any, content_hash: str) -> bool:
    if not content_hash:
        return False
    result = collection.get(
        where={"content_hash": content_hash},
        include=[],
    )
    return bool(result.get("ids"))


def filter_duplicate_chunks(
    collection: Any,
    chunks: list[Chunk],
    *,
    batch_size: int = 100,
) -> DuplicateCheckResult:
    if not chunks:
        return DuplicateCheckResult(new_chunks=[], skipped_by_id=0, skipped_by_hash=0)

    existing_ids: set[str] = set()
    for batch in _batched([chunk.id for chunk in chunks], batch_size):
        result = collection.get(ids=batch, include=[])
        existing_ids.update(result.get("ids") or [])

    seen_hashes_in_batch: set[str] = set()
    new_chunks: list[Chunk] = []
    skipped_by_id = 0
    skipped_by_hash = 0

    for chunk in chunks:
        if chunk.id in existing_ids:
            skipped_by_id += 1
            continue

        content_hash = str(chunk.metadata.get("content_hash") or "")
        if content_hash and (content_hash in seen_hashes_in_batch or _content_hash_exists(collection, content_hash)):
            skipped_by_hash += 1
            continue

        if content_hash:
            seen_hashes_in_batch.add(content_hash)
        new_chunks.append(chunk)

    return DuplicateCheckResult(
        new_chunks=new_chunks,
        skipped_by_id=skipped_by_id,
        skipped_by_hash=skipped_by_hash,
    )
