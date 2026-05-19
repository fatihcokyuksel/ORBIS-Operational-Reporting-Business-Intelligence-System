from __future__ import annotations

import logging
import re
from dataclasses import replace

from rag_preprocess.config import (
    MAX_MODEL_TOKENS,
    PARAGRAPH_MARKER_PATTERN,
    SPLIT_OVERLAP_TOKENS,
    TARGET_CHUNK_TOKENS,
)
from rag_preprocess.models import Article, Chunk
from rag_preprocess.token_counter import TokenCounter

logger = logging.getLogger(__name__)
PARAGRAPH_MARKER_RE = re.compile(PARAGRAPH_MARKER_PATTERN)


def _metadata_value(value: object) -> object:
    return value


def _format_header_for_articles(articles: list[Article]) -> str:
    first = articles[0]
    article_numbers = [article.article_no for article in articles]
    lines = [
        f"Kanun: {first.official_name}",
        f"Kanun No: {first.law_no or ''}",
    ]

    chapter_names = {article.chapter_name for article in articles if article.chapter_name}
    section_names = {article.section_name for article in articles if article.section_name}
    if chapter_names:
        lines.append(f"Kısım: {' / '.join(sorted(chapter_names))}")
    if section_names:
        lines.append(f"Bölüm: {' / '.join(sorted(section_names))}")

    if len(articles) == 1:
        article = articles[0]
        lines.append(f"Madde: {article.article_no}")
        if article.article_title:
            lines.append(f"Madde Başlığı: {article.article_title}")
    else:
        lines.append(f"Maddeler: {', '.join(article_numbers)}")
    return "\n".join(lines)


def build_chunk_text_for_articles(articles: list[Article]) -> str:
    header = _format_header_for_articles(articles)
    body = "\n\n".join(article.text.strip() for article in articles if article.text.strip())
    return f"{header}\n\n{body}".strip()


def build_article_part_text(article: Article, part_text: str, part_index: int, part_total: int) -> str:
    lines = [
        f"Kanun: {article.official_name}",
        f"Kanun No: {article.law_no or ''}",
    ]
    if article.chapter_name:
        lines.append(f"Kısım: {article.chapter_name}")
    if article.section_name:
        lines.append(f"Bölüm: {article.section_name}")
    lines.append(f"Madde: {article.article_no}")
    if article.article_title:
        lines.append(f"Madde Başlığı: {article.article_title}")
    lines.append(f"Madde Parçası: {part_index}/{part_total}")
    return f"{chr(10).join(lines)}\n\n{part_text.strip()}".strip()


def _included_articles_padded(article_numbers: list[str]) -> str:
    return "|" + "|".join(article_numbers) + "|"


def _chunk_id(
    *,
    document_id: str,
    article_numbers: list[str],
    chunk_index: int,
    article_part: int | None = None,
) -> str:
    if article_part is not None:
        return (
            f"{document_id}_article_{article_numbers[0]}_part_{article_part}"
            f"_chunk_{chunk_index}"
        )
    if len(article_numbers) == 1:
        return f"{document_id}_article_{article_numbers[0]}_chunk_{chunk_index}"
    return (
        f"{document_id}_articles_{article_numbers[0]}_{article_numbers[-1]}"
        f"_chunk_{chunk_index}"
    )


def _build_chunk(
    *,
    articles: list[Article],
    text: str,
    token_count: int,
    chunk_index: int,
    chunk_type: str,
    is_article_split: bool,
    article_part: int | None = None,
    article_part_total: int | None = None,
) -> Chunk:
    first = articles[0]
    article_numbers = [article.article_no for article in articles]
    metadata = {
        "document_id": first.document_id,
        "document_type": first.document_type,
        "law_no": _metadata_value(first.law_no),
        "law_name": first.law_name,
        "official_name": first.official_name,
        "article_no": first.article_no if len(articles) == 1 else None,
        "article_title": first.article_title if len(articles) == 1 else None,
        "included_articles": ",".join(article_numbers),
        "included_articles_padded": _included_articles_padded(article_numbers),
        "start_article": article_numbers[0],
        "end_article": article_numbers[-1],
        "section_name": first.section_name,
        "chapter_name": first.chapter_name,
        "page_start": min(article.page_start for article in articles),
        "page_end": max(article.page_end for article in articles),
        "source_file": first.source_file,
        "source_url": first.source_url,
        "token_count": token_count,
        "chunk_index": chunk_index,
        "chunk_type": chunk_type,
        "is_article_split": is_article_split,
        "article_part": article_part,
        "article_part_total": article_part_total,
    }
    return Chunk(
        id=_chunk_id(
            document_id=first.document_id,
            article_numbers=article_numbers,
            chunk_index=chunk_index,
            article_part=article_part,
        ),
        text=text,
        metadata=metadata,
    )


def _split_article_into_units(article_text: str) -> list[str]:
    lines = article_text.splitlines()
    units: list[str] = []
    current: list[str] = []

    for line in lines:
        if PARAGRAPH_MARKER_RE.match(line) and current:
            units.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)

    if current:
        units.append("\n".join(current).strip())

    if len(units) <= 1:
        units = [part.strip() for part in re.split(r"\n\s*\n|\n(?=[A-ZÇĞİÖŞÜ0-9])", article_text) if part.strip()]

    return units or [article_text]


def split_long_article(article: Article, token_counter: TokenCounter) -> list[Chunk]:
    header_probe = build_article_part_text(article, "", 1, 1)
    header_tokens = token_counter.count_tokens(header_probe)
    body_limit = max(256, MAX_MODEL_TOKENS - header_tokens - 32)
    packing_limit = max(128, body_limit - SPLIT_OVERLAP_TOKENS)

    units = _split_article_into_units(article.text)
    raw_parts: list[str] = []
    current_units: list[str] = []

    def current_text() -> str:
        return "\n\n".join(current_units).strip()

    def flush_current() -> None:
        nonlocal current_units
        text = current_text()
        if text:
            raw_parts.append(text)
        current_units = []

    for unit in units:
        if token_counter.count_tokens(unit) > packing_limit:
            flush_current()
            raw_parts.extend(
                token_counter.split_text_by_tokens(
                    unit,
                    max_tokens=packing_limit,
                    overlap_tokens=0,
                )
            )
            continue

        candidate_units = current_units + [unit]
        candidate = "\n\n".join(candidate_units).strip()
        if token_counter.count_tokens(candidate) <= packing_limit:
            current_units = candidate_units
        else:
            flush_current()
            current_units = [unit]
    flush_current()

    parts_with_overlap: list[str] = []
    for index, raw_part in enumerate(raw_parts):
        part = raw_part
        if index > 0:
            overlap = token_counter.tail_text(raw_parts[index - 1], SPLIT_OVERLAP_TOKENS)
            part = f"{overlap}\n\n{raw_part}".strip()
        if token_counter.count_tokens(part) > body_limit:
            part = token_counter.head_text(part, body_limit)
        parts_with_overlap.append(part)

    total = len(parts_with_overlap)
    chunks: list[Chunk] = []
    for index, part_text in enumerate(parts_with_overlap, start=1):
        text = build_article_part_text(article, part_text, index, total)
        token_count = token_counter.count_tokens(text)
        if token_count > MAX_MODEL_TOKENS:
            trimmed_body_limit = max(128, body_limit - (token_count - MAX_MODEL_TOKENS) - 8)
            text = build_article_part_text(
                article,
                token_counter.head_text(part_text, trimmed_body_limit),
                index,
                total,
            )
            token_count = token_counter.count_tokens(text)
        chunks.append(
            _build_chunk(
                articles=[article],
                text=text,
                token_count=token_count,
                chunk_index=0,
                chunk_type="article_part",
                is_article_split=True,
                article_part=index,
                article_part_total=total,
            )
        )
    return chunks


def chunk_articles(
    articles: list[Article],
    token_counter: TokenCounter,
    *,
    target_chunk_tokens: int = TARGET_CHUNK_TOKENS,
    max_model_tokens: int = MAX_MODEL_TOKENS,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    current_articles: list[Article] = []
    chunk_index = 1

    def flush_current() -> None:
        nonlocal current_articles, chunk_index
        if not current_articles:
            return
        text = build_chunk_text_for_articles(current_articles)
        token_count = token_counter.count_tokens(text)
        chunk_type = "single_article" if len(current_articles) == 1 else "multi_article"
        chunks.append(
            _build_chunk(
                articles=current_articles,
                text=text,
                token_count=token_count,
                chunk_index=chunk_index,
                chunk_type=chunk_type,
                is_article_split=False,
            )
        )
        chunk_index += 1
        current_articles = []

    for article in articles:
        article_text = build_chunk_text_for_articles([article])
        article_token_count = token_counter.count_tokens(article_text)

        if article_token_count > max_model_tokens:
            flush_current()
            part_chunks = split_long_article(article, token_counter)
            for part_chunk in part_chunks:
                updated_metadata = dict(part_chunk.metadata)
                updated_metadata["chunk_index"] = chunk_index
                updated_chunk = replace(
                    part_chunk,
                    id=_chunk_id(
                        document_id=article.document_id,
                        article_numbers=[article.article_no],
                        chunk_index=chunk_index,
                        article_part=updated_metadata["article_part"],
                    ),
                    metadata=updated_metadata,
                )
                chunks.append(updated_chunk)
                chunk_index += 1
            continue

        if article_token_count > target_chunk_tokens:
            flush_current()
            chunks.append(
                _build_chunk(
                    articles=[article],
                    text=article_text,
                    token_count=article_token_count,
                    chunk_index=chunk_index,
                    chunk_type="single_article_long",
                    is_article_split=False,
                )
            )
            chunk_index += 1
            continue

        if not current_articles:
            current_articles = [article]
            continue

        candidate_articles = current_articles + [article]
        candidate_text = build_chunk_text_for_articles(candidate_articles)
        if token_counter.count_tokens(candidate_text) <= target_chunk_tokens:
            current_articles = candidate_articles
        else:
            flush_current()
            current_articles = [article]

    flush_current()
    logger.info("Article-aware chunking tamamlandı: chunk_count=%d", len(chunks))
    return chunks
