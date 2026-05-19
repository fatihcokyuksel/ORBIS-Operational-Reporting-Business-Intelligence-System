from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_LAW_ALIASES = {
    "VUK": "Vergi Usul Kanunu",
    "VERGI USUL KANUNU": "Vergi Usul Kanunu",
    "VERGIUSULKANUNU": "Vergi Usul Kanunu",
    "TCK": "Turk Ceza Kanunu",
    "TURK CEZA KANUNU": "Turk Ceza Kanunu",
    "TURKCEZAKANUNU": "Turk Ceza Kanunu",
    "TTK": "Turk Ticaret Kanunu",
    "TURK TICARET KANUNU": "Turk Ticaret Kanunu",
    "TURKTICARETKANUNU": "Turk Ticaret Kanunu",
    "KVKK": "Kisisel Verilerin Korunmasi Kanunu",
    "KISISSEL VERILERIN KORUNMASI KANUNU": "Kisisel Verilerin Korunmasi Kanunu",
    "IS KANUNU": "Is Kanunu",
    "TURK BORCLAR KANUNU": "Turk Borclar Kanunu",
}


@dataclass(slots=True)
class RagSettings:
    project_root: Path
    chroma_db_path: Path
    chroma_collection_name: str
    embedding_model_name: str
    embedding_batch_size: int
    chroma_add_batch_size: int
    max_model_tokens: int
    migration_backup_dir: Path
    language: str = "tr"
    law_aliases: dict[str, str] = field(default_factory=dict)


def _resolve_path(value: str | None, project_root: Path, default_relative: str) -> Path:
    raw = (value or default_relative).strip()
    path = Path(raw)
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def _parse_aliases(raw: str | None) -> dict[str, str]:
    aliases = dict(DEFAULT_LAW_ALIASES)
    if not raw:
        return aliases

    try:
        user_aliases = json.loads(raw)
    except json.JSONDecodeError:
        return aliases

    if not isinstance(user_aliases, dict):
        return aliases

    for key, value in user_aliases.items():
        if not isinstance(key, str) or not isinstance(value, str):
            continue
        aliases[key.strip().upper()] = value.strip()
    return aliases


def get_rag_settings(project_root: Path | None = None) -> RagSettings:
    resolved_root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    chroma_db_path = _resolve_path(
        os.getenv("CHROMA_DB_PATH"),
        resolved_root,
        "chroma_local_kanun_db",
    )
    migration_backup_dir = _resolve_path(
        os.getenv("CHROMA_MIGRATION_BACKUP_DIR"),
        resolved_root,
        "storage/chroma_backups",
    )
    return RagSettings(
        project_root=resolved_root,
        chroma_db_path=chroma_db_path,
        chroma_collection_name=os.getenv("CHROMA_COLLECTION_NAME", "kanun_embedding").strip() or "kanun_embedding",
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-m3").strip() or "BAAI/bge-m3",
        embedding_batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "32")),
        chroma_add_batch_size=int(os.getenv("CHROMA_ADD_BATCH_SIZE", "100")),
        max_model_tokens=int(os.getenv("MAX_MODEL_TOKENS", "8192")),
        migration_backup_dir=migration_backup_dir,
        language=os.getenv("RAG_LANGUAGE", "tr").strip() or "tr",
        law_aliases=_parse_aliases(os.getenv("LAW_ALIASES_JSON")),
    )
