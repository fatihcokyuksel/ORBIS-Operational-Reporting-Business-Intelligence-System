from __future__ import annotations

import logging
import re

from rag_preprocess.config import (
    ARTICLE_PATTERN,
    CHAPTER_PATTERN,
    INTRO_PATTERN,
    LAW_NO_PATTERN,
    SECTION_PATTERN,
)
from rag_preprocess.models import Article, LawMetadata, PageLine, PageText

logger = logging.getLogger(__name__)

ARTICLE_RE = re.compile(ARTICLE_PATTERN)
CHAPTER_RE = re.compile(CHAPTER_PATTERN)
SECTION_RE = re.compile(SECTION_PATTERN)
INTRO_RE = re.compile(INTRO_PATTERN)
LAW_NO_RE = re.compile(LAW_NO_PATTERN)


def normalize_article_prefix(prefix: str) -> str:
    upper = prefix.upper()
    if "GEÇ" in upper:
        return "Geçici Madde"
    if "MÜK" in upper:
        return "Mükerrer Madde"
    if upper.startswith("EK"):
        return "Ek Madde"
    return "Madde"


def _is_title_candidate(line: PageLine | None) -> bool:
    if line is None:
        return False

    text = line.text.strip()
    title = text.rstrip(":").strip()
    if len(title) < 3 or len(title) > 140:
        return False
    if ARTICLE_RE.match(text) or CHAPTER_RE.match(text) or SECTION_RE.match(text):
        return False
    if INTRO_RE.match(text) or LAW_NO_RE.search(text):
        return False
    upper = text.upper()
    blocked_fragments = [
        "RESMİ GAZETE",
        "YAYIMLANDIĞI",
        "KABUL TARİHİ",
        "KANUN NUMARASI",
    ]
    if any(fragment in upper for fragment in blocked_fragments):
        return False
    if text.endswith(":"):
        return True
    if len(title.split()) <= 12 and not text.endswith((".", ";", ",")):
        return True
    return False


def _clean_article_title(line: PageLine | None) -> str | None:
    if not _is_title_candidate(line):
        return None
    assert line is not None
    return line.text.rstrip(":").strip() or None


def _join_article_lines(lines: list[PageLine]) -> str:
    return "\n".join(line.text for line in lines).strip()


def extract_articles(pages: list[PageText], metadata: LawMetadata) -> list[Article]:
    flattened_lines = [line for page in pages for line in page.lines]
    articles: list[Article] = []

    current_chapter: str | None = None
    current_section: str | None = None
    current_info: dict[str, str | None] | None = None
    current_lines: list[PageLine] = []
    last_nonempty_line: PageLine | None = None

    def close_current_article() -> None:
        nonlocal current_info, current_lines
        if current_info is None or not current_lines:
            current_info = None
            current_lines = []
            return

        article_text = _join_article_lines(current_lines)
        if not article_text:
            current_info = None
            current_lines = []
            return

        articles.append(
            Article(
                document_id=metadata.document_id,
                document_type=metadata.document_type,
                law_no=metadata.law_no,
                law_name=metadata.law_name,
                official_name=metadata.official_name,
                article_no=str(current_info["article_no"]),
                article_prefix=str(current_info["article_prefix"]),
                article_title=current_info.get("article_title"),
                chapter_name=current_info.get("chapter_name"),
                section_name=current_info.get("section_name"),
                page_start=current_lines[0].page,
                page_end=current_lines[-1].page,
                source_file=metadata.source_file,
                source_url=metadata.source_url,
                text=article_text,
            )
        )
        current_info = None
        current_lines = []

    for line in flattened_lines:
        text = line.text

        chapter_match = CHAPTER_RE.match(text)
        if chapter_match:
            current_chapter = chapter_match.group("chapter").strip()
            last_nonempty_line = line
            continue

        section_match = SECTION_RE.match(text)
        if section_match:
            current_section = section_match.group("section").strip()
            last_nonempty_line = line
            continue

        intro_match = INTRO_RE.match(text)
        if intro_match:
            current_chapter = intro_match.group("intro").strip()
            last_nonempty_line = line
            continue

        article_match = ARTICLE_RE.match(text)
        if article_match:
            title = _clean_article_title(last_nonempty_line)
            if title and current_lines and last_nonempty_line == current_lines[-1]:
                current_lines.pop()

            close_current_article()

            current_info = {
                "article_no": article_match.group("article_no").strip(),
                "article_prefix": normalize_article_prefix(article_match.group("prefix")),
                "article_title": title,
                "chapter_name": current_chapter,
                "section_name": current_section,
            }
            current_lines = [line]
            last_nonempty_line = line
            continue

        if current_info is not None:
            current_lines.append(line)
        last_nonempty_line = line

    close_current_article()
    logger.info(
        "Madde çıkarımı tamamlandı: source=%s, article_count=%d",
        metadata.source_file,
        len(articles),
    )
    return articles
