from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from rag_preprocess.config import (
    FILENAME_LAW_NAME_MAPPING,
    KNOWN_LAW_TITLES,
    LAW_NO_PATTERN,
)
from rag_preprocess.models import LawMetadata, PageText


TURKISH_TRANSLATION = str.maketrans(
    {
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "I": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
    }
)

TURKISH_LOWER_TRANSLATION = str.maketrans({"I": "ı", "İ": "i"})
TURKISH_INITIAL_UPPER = {
    "i": "İ",
    "ı": "I",
    "ç": "Ç",
    "ğ": "Ğ",
    "ö": "Ö",
    "ş": "Ş",
    "ü": "Ü",
}


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    value = value.translate(TURKISH_TRANSLATION)
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "document"


def title_case_tr(text: str) -> str:
    words: list[str] = []
    for part in text.split():
        lowered = part.translate(TURKISH_LOWER_TRANSLATION).lower()
        if not lowered:
            continue
        first = TURKISH_INITIAL_UPPER.get(lowered[0], lowered[0].upper())
        words.append(first + lowered[1:])
    return " ".join(words)


def extract_law_no(text: str, filename_stem: str) -> str | None:
    match = re.search(LAW_NO_PATTERN, text)
    if match:
        return match.group("law_no")
    if filename_stem in FILENAME_LAW_NAME_MAPPING:
        return filename_stem
    filename_match = re.search(r"\d+", filename_stem)
    return filename_match.group(0) if filename_match else None


def extract_law_name(text: str, law_no: str | None, filename_stem: str) -> str:
    upper_text = text.upper()
    for title in KNOWN_LAW_TITLES:
        if title in upper_text:
            return title_case_tr(title)

    title_candidates: list[str] = []
    for line in text.splitlines()[:80]:
        stripped = line.strip()
        upper = stripped.upper()
        if (
            "KANUNU" in upper
            and "KANUN NUMARASI" not in upper
            and 8 <= len(stripped) <= 160
        ):
            title_candidates.append(stripped)

    if title_candidates:
        best = max(title_candidates, key=len)
        return title_case_tr(best)

    if law_no and law_no in FILENAME_LAW_NAME_MAPPING:
        return FILENAME_LAW_NAME_MAPPING[law_no]
    if filename_stem in FILENAME_LAW_NAME_MAPPING:
        return FILENAME_LAW_NAME_MAPPING[filename_stem]
    return filename_stem.replace("_", " ").replace("-", " ").title()


def extract_law_metadata(pdf_path: Path, pages: list[PageText]) -> LawMetadata:
    first_pages_text = "\n".join(page.text for page in pages[:2])
    law_no = extract_law_no(first_pages_text, pdf_path.stem)
    law_name = extract_law_name(first_pages_text, law_no, pdf_path.stem)
    official_name = f"{law_no} Sayılı {law_name}" if law_no else law_name
    slug = slugify(law_name)
    document_id = f"law_{law_no}_{slug}" if law_no else f"doc_{slugify(pdf_path.stem)}"

    return LawMetadata(
        document_id=document_id,
        document_type="law" if law_no else "unknown",
        law_no=law_no,
        law_name=law_name,
        official_name=official_name,
        source_file=pdf_path.name,
        source_url=None,
    )
