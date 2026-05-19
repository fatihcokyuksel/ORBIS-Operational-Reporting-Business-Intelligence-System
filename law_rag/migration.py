from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from law_rag.chroma_manager import get_collection
from law_rag.config import RagSettings
from law_rag.metadata import build_standard_metadata


def create_chroma_backup(settings: RagSettings) -> Path:
    settings.migration_backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_path = settings.migration_backup_dir / f"{settings.chroma_db_path.name}_{stamp}"
    shutil.copytree(settings.chroma_db_path, backup_path)
    return backup_path


def restore_chroma_backup(settings: RagSettings, backup_path: Path) -> None:
    if settings.chroma_db_path.exists():
        shutil.rmtree(settings.chroma_db_path)
    shutil.copytree(backup_path, settings.chroma_db_path)


def migrate_collection_metadata(settings: RagSettings, *, batch_size: int = 100) -> dict[str, Any]:
    backup_path = create_chroma_backup(settings)
    collection = get_collection(settings)
    total_count = collection.count()
    migrated_count = 0

    for offset in range(0, total_count, batch_size):
        result = collection.get(
            limit=batch_size,
            offset=offset,
            include=["documents", "metadatas"],
        )
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        metadatas = result.get("metadatas") or []
        updated_metadatas = []
        for metadata, document in zip(metadatas, documents):
            updated_metadatas.append(
                build_standard_metadata(
                    dict(metadata or {}),
                    str(document or ""),
                    embedding_model_name=settings.embedding_model_name,
                    language=settings.language,
                    aliases=settings.law_aliases,
                )
            )
        if ids:
            collection.update(ids=ids, metadatas=updated_metadatas)
            migrated_count += len(ids)

    return {
        "backup_path": str(backup_path),
        "collection_name": settings.chroma_collection_name,
        "migrated_count": migrated_count,
        "total_count": total_count,
    }
