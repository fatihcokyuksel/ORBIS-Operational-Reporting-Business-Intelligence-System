from __future__ import annotations

import logging
from pathlib import Path

from rag_preprocess.models import PageLine, PageText
from rag_preprocess.text_cleaner import (
    clean_line,
    detect_repeated_header_footer_lines,
    filter_page_lines,
)

logger = logging.getLogger(__name__)


def _require_fitz():
    try:
        import fitz  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF kurulu değil. Lütfen `pip install pymupdf` komutuyla kurun."
        ) from exc
    return fitz


def load_pdf_pages(pdf_path: Path) -> list[PageText]:
    fitz = _require_fitz()
    logger.info("PDF parse başladı: %s", pdf_path.name)

    raw_pages: list[list[str]] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text("text", sort=True)
            raw_pages.append([clean_line(line) for line in text.splitlines()])

    preliminary_pages: list[list[PageLine]] = [
        filter_page_lines(lines, page_number=index + 1)
        for index, lines in enumerate(raw_pages)
    ]
    repeated = detect_repeated_header_footer_lines(preliminary_pages)

    pages: list[PageText] = []
    for index, raw_lines in enumerate(raw_pages, start=1):
        lines = filter_page_lines(raw_lines, page_number=index, repeated_lines=repeated)
        pages.append(
            PageText(
                page=index,
                text="\n".join(line.text for line in lines),
                lines=lines,
            )
        )

    logger.info("PDF parse tamamlandı: %s, sayfa=%d", pdf_path.name, len(pages))
    return pages
