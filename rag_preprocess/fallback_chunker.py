from __future__ import annotations

import logging
from pathlib import Path

from rag_preprocess.config import FALLBACK_OVERLAP_TOKENS, TARGET_CHUNK_TOKENS
from rag_preprocess.models import Chunk, LawMetadata, PageLine, PageText
from rag_preprocess.token_counter import TokenCounter

logger = logging.getLogger(__name__)


def _fallback_header(metadata: LawMetadata) -> str:
    lines = [
        f"Kaynak: {metadata.official_name or metadata.source_file}",
    ]
    if metadata.law_no:
        lines.append(f"Kanun No: {metadata.law_no}")
    return "\n".join(lines)


def _metadata_for_fallback(
    *,
    metadata: LawMetadata,
    chunk_index: int,
    token_count: int,
    page_start: int,
    page_end: int,
) -> dict[str, object]:
    return {
        "document_id": metadata.document_id,
        "document_type": "standard_or_note" if not metadata.law_no else metadata.document_type,
        "law_no": metadata.law_no,
        "law_name": metadata.law_name,
        "official_name": metadata.official_name,
        "article_no": None,
        "article_title": None,
        "included_articles": "",
        "included_articles_padded": "",
        "start_article": None,
        "end_article": None,
        "section_name": None,
        "chapter_name": None,
        "page_start": page_start,
        "page_end": page_end,
        "source_file": metadata.source_file,
        "source_url": metadata.source_url,
        "token_count": token_count,
        "chunk_index": chunk_index,
        "chunk_type": "fallback_text_chunk",
        "is_article_split": False,
        "article_part": None,
        "article_part_total": None,
    }


def _line_to_unit(line: PageLine) -> tuple[str, int, int]:
    return line.text, line.page, line.page


def fallback_chunk_pages(
    pages: list[PageText],
    metadata: LawMetadata,
    token_counter: TokenCounter,
    *,
    target_chunk_tokens: int = TARGET_CHUNK_TOKENS,
    overlap_tokens: int = FALLBACK_OVERLAP_TOKENS,
) -> list[Chunk]:
    units = [_line_to_unit(line) for page in pages for line in page.lines if line.text.strip()]
    header = _fallback_header(metadata)
    header_tokens = token_counter.count_tokens(header)
    content_limit = max(128, target_chunk_tokens - header_tokens - 8)

    chunks: list[Chunk] = []
    current_texts: list[str] = []
    current_pages: list[int] = []
    current_is_overlap_only = False

    def current_body() -> str:
        return "\n".join(current_texts).strip()

    def flush_current() -> None:
        nonlocal current_texts, current_pages, current_is_overlap_only
        body = current_body()
        if not body:
            current_texts = []
            current_pages = []
            current_is_overlap_only = False
            return

        chunk_index = len(chunks) + 1
        text = f"{header}\n\n{body}".strip()
        token_count = token_counter.count_tokens(text)
        page_start = min(current_pages)
        page_end = max(current_pages)
        chunks.append(
            Chunk(
                id=f"{metadata.document_id}_fallback_chunk_{chunk_index}",
                text=text,
                metadata=_metadata_for_fallback(
                    metadata=metadata,
                    chunk_index=chunk_index,
                    token_count=token_count,
                    page_start=page_start,
                    page_end=page_end,
                ),
            )
        )

        overlap_text = token_counter.tail_text(body, overlap_tokens)
        current_texts = [overlap_text] if overlap_text else []
        current_pages = [page_end] if overlap_text else []
        current_is_overlap_only = bool(overlap_text)

    for unit_text, page_start, page_end in units:
        if token_counter.count_tokens(unit_text) > content_limit:
            flush_current()
            split_units = token_counter.split_text_by_tokens(
                unit_text,
                max_tokens=content_limit,
                overlap_tokens=overlap_tokens,
            )
            for split_unit in split_units:
                current_texts = [split_unit]
                current_pages = [page_start, page_end]
                current_is_overlap_only = False
                flush_current()
            continue

        candidate_body = "\n".join(current_texts + [unit_text]).strip()
        if token_counter.count_tokens(candidate_body) <= content_limit:
            current_texts.append(unit_text)
            current_pages.extend([page_start, page_end])
            current_is_overlap_only = False
        else:
            flush_current()
            current_texts.append(unit_text)
            current_pages.extend([page_start, page_end])
            current_is_overlap_only = False

    if current_texts and not current_is_overlap_only:
        body = current_body()
        chunk_index = len(chunks) + 1
        text = f"{header}\n\n{body}".strip()
        token_count = token_counter.count_tokens(text)
        page_start = min(current_pages)
        page_end = max(current_pages)
        chunks.append(
            Chunk(
                id=f"{metadata.document_id}_fallback_chunk_{chunk_index}",
                text=text,
                metadata=_metadata_for_fallback(
                    metadata=metadata,
                    chunk_index=chunk_index,
                    token_count=token_count,
                    page_start=page_start,
                    page_end=page_end,
                ),
            )
        )

    logger.info(
        "Fallback chunking tamamlandı: source=%s, chunk_count=%d",
        Path(metadata.source_file).name,
        len(chunks),
    )
    return chunks
