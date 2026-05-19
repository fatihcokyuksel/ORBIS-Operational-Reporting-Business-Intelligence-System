from __future__ import annotations

import re
import unicodedata
from collections import Counter

from rag_preprocess.models import PageLine


PAGE_NUMBER_RE = re.compile(r"^\s*(?:-?\s*)?\d{1,4}(?:\s*-?)?\s*$")
REPEATED_WHITESPACE_RE = re.compile(r"[ \t]+")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u00a0", " ")
    text = text.replace("\ufeff", "")
    text = text.replace("‐", "-")
    return text


def clean_line(text: str) -> str:
    text = normalize_text(text)
    text = REPEATED_WHITESPACE_RE.sub(" ", text)
    return text.strip()


def is_page_number_line(text: str) -> bool:
    return bool(PAGE_NUMBER_RE.fullmatch(text.strip()))


def normalize_for_repeated_line_detection(text: str) -> str:
    text = clean_line(text).casefold()
    return re.sub(r"\d+", "#", text)


def detect_repeated_header_footer_lines(
    pages: list[list[PageLine]],
    *,
    min_page_ratio: float = 0.35,
) -> set[str]:
    if len(pages) < 4:
        return set()

    candidates: Counter[str] = Counter()
    for page_lines in pages:
        edge_lines = page_lines[:3] + page_lines[-3:]
        seen_on_page: set[str] = set()
        for line in edge_lines:
            normalized = normalize_for_repeated_line_detection(line.text)
            if 5 <= len(normalized) <= 140:
                seen_on_page.add(normalized)
        candidates.update(seen_on_page)

    min_count = max(2, int(len(pages) * min_page_ratio))
    return {line for line, count in candidates.items() if count >= min_count}


def filter_page_lines(
    raw_lines: list[str],
    *,
    page_number: int,
    repeated_lines: set[str] | None = None,
) -> list[PageLine]:
    repeated_lines = repeated_lines or set()
    cleaned: list[PageLine] = []
    for original_line_no, raw_line in enumerate(raw_lines, start=1):
        line = clean_line(raw_line)
        if not line:
            continue
        if is_page_number_line(line):
            continue
        if normalize_for_repeated_line_detection(line) in repeated_lines:
            continue
        cleaned.append(PageLine(page=page_number, line_no=original_line_no, text=line))
    return cleaned
