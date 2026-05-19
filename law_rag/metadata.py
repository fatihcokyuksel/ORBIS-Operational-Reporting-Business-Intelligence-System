from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ARTICLE_NO_RE = re.compile(r"(?i)\bmadde\s*[:\-]?\s*(\d+[\/A-Z0-9a-zçğıöşü]*)")
KANUN_NO_RE = re.compile(r"(?i)\bkanun\s*(?:no|numarasi|numarası)?\s*[:\-]?\s*(\d{3,5})")
ARTICLE_REF_RE = re.compile(r"(?i)\b(?:madde|md\.?)\s*(\d+[\/A-Z0-9a-zçğıöşü]*)")

TURKISH_ASCII_MAP = str.maketrans(
    {
        "ç": "c",
        "Ç": "C",
        "ğ": "g",
        "Ğ": "G",
        "ı": "i",
        "İ": "I",
        "ö": "o",
        "Ö": "O",
        "ş": "s",
        "Ş": "S",
        "ü": "u",
        "Ü": "U",
    }
)


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFC", str(value or "")).translate(TURKISH_ASCII_MAP)
    text = re.sub(r"[^0-9A-Za-z]+", " ", text).strip().upper()
    return re.sub(r"\s+", " ", text)


def slugify_for_hash(value: str | None) -> str:
    normalized = normalize_text(value).lower()
    return re.sub(r"\s+", "_", normalized).strip("_")


def normalize_law_name(value: str | None, aliases: dict[str, str] | None = None) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    alias_value = (aliases or {}).get(normalized)
    if alias_value:
        return normalize_text(alias_value)
    return normalized


def infer_article_no(metadata: dict[str, Any], text: str) -> str:
    for key in ("madde_no", "article_no", "start_article"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value

    combined = " ".join(
        [
            str(metadata.get("article_title") or ""),
            text[:500],
        ]
    )
    for pattern in (ARTICLE_NO_RE, ARTICLE_REF_RE):
        match = pattern.search(combined)
        if match:
            return match.group(1).strip()
    return ""


def infer_law_no(metadata: dict[str, Any], text: str) -> str:
    for key in ("law_no", "kanun_no"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value

    source = str(metadata.get("source") or metadata.get("source_file") or "")
    source_match = re.search(r"\b(\d{3,5})\b", source)
    if source_match:
        return source_match.group(1)

    match = KANUN_NO_RE.search(text[:800])
    return match.group(1).strip() if match else ""


def infer_law_name(metadata: dict[str, Any]) -> str:
    for key in ("kanun_adi", "law_name", "official_name", "document_name"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    source = str(metadata.get("source_file") or metadata.get("source") or metadata.get("original_file") or "")
    return Path(source).stem.replace("_", " ").replace("-", " ").strip()


def infer_page(metadata: dict[str, Any]) -> int | None:
    for key in ("page", "page_start", "sayfa"):
        value = metadata.get(key)
        if value in (None, ""):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def infer_section(metadata: dict[str, Any]) -> str:
    for key in ("section", "section_name", "chapter_name"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def compute_content_hash(text: str, metadata: dict[str, Any]) -> str:
    digest_base = "||".join(
        [
            str(metadata.get("document_id") or ""),
            str(metadata.get("law_no") or ""),
            str(metadata.get("article_no") or metadata.get("madde_no") or ""),
            text.strip(),
        ]
    )
    return hashlib.sha256(digest_base.encode("utf-8")).hexdigest()


def build_standard_metadata(
    metadata: dict[str, Any],
    text: str,
    *,
    embedding_model_name: str,
    language: str,
    aliases: dict[str, str] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    standard = dict(metadata)
    kanun_adi = infer_law_name(standard)
    kanun_no = infer_law_no(standard, text)
    madde_no = infer_article_no(standard, text)
    page = infer_page(standard)
    section = infer_section(standard)
    source_file = str(
        standard.get("source_file")
        or standard.get("source")
        or standard.get("original_file")
        or ""
    ).strip()

    standard.update(
        {
            "document_name": str(standard.get("document_name") or kanun_adi or source_file).strip(),
            "source_file": source_file,
            "kanun_adi": kanun_adi,
            "kanun_no": kanun_no,
            "kanun_adi_normalized": normalize_law_name(kanun_adi, aliases),
            "madde_no": madde_no,
            "section": section,
            "chunk_index": int(standard.get("chunk_index") or 0),
            "page": page if page is not None else "",
            "embedding_model": embedding_model_name,
            "created_at": created_at or datetime.now(UTC).isoformat(),
            "content_type": str(standard.get("content_type") or standard.get("document_type") or "kanun"),
            "language": language,
        }
    )
    standard["content_hash"] = compute_content_hash(text, standard)
    standard["document_key"] = slugify_for_hash(f"{kanun_no}_{kanun_adi}_{source_file}")
    return standard


def sanitize_metadata_for_chroma(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    sanitized: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            sanitized[key] = ""
        elif isinstance(value, bool):
            sanitized[key] = value
        elif isinstance(value, int):
            sanitized[key] = value
        elif isinstance(value, float):
            sanitized[key] = value
        else:
            sanitized[key] = str(value)
    return sanitized
