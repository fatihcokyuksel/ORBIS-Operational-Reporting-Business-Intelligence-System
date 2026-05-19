from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from rag_preprocess.models import Article, Chunk, PageText


def ensure_directories(paths: Iterable[Path]) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_articles_json(path: Path, articles: list[Article]) -> None:
    write_json(path, [article.to_dict() for article in articles])


def write_pages_json(path: Path, pages: list[PageText]) -> None:
    write_json(path, [page.to_dict() for page in pages])


def write_chunks_jsonl(path: Path, chunks: list[Chunk]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.to_dict(), ensure_ascii=False))
            handle.write("\n")
