from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any

from rag_preprocess.config import COLLECTION_NAME
from rag_preprocess.models import Article, Chunk, LawMetadata


def build_quality_report(
    *,
    metadata: LawMetadata,
    articles: list[Article],
    chunks: list[Chunk],
    failed_articles: list[str] | None = None,
) -> dict[str, Any]:
    failed_articles = failed_articles or []
    token_counts = [int(chunk.metadata.get("token_count") or 0) for chunk in chunks]

    def count_type(chunk_type: str) -> int:
        return sum(1 for chunk in chunks if chunk.metadata.get("chunk_type") == chunk_type)

    return {
        "source_file": metadata.source_file,
        "law_no": metadata.law_no,
        "law_name": metadata.law_name,
        "article_count": len(articles),
        "chunk_count": len(chunks),
        "multi_article_chunk_count": count_type("multi_article"),
        "single_article_chunk_count": count_type("single_article"),
        "single_article_long_chunk_count": count_type("single_article_long"),
        "article_part_chunk_count": count_type("article_part"),
        "fallback_chunk_count": count_type("fallback_text_chunk"),
        "max_token_count": max(token_counts) if token_counts else 0,
        "avg_token_count": round(mean(token_counts), 2) if token_counts else 0,
        "failed_articles": failed_articles,
    }


def build_global_report(
    *,
    selected_directory: Path,
    output_directory: Path,
    processed_pdf_count: int,
    failed_files: list[dict[str, str]],
    total_article_count: int,
    total_chunk_count: int,
    chroma_db_path: Path,
    all_chunks_jsonl: Path,
    collection_name: str = COLLECTION_NAME,
) -> dict[str, Any]:
    return {
        "selected_directory": str(selected_directory),
        "output_directory": str(output_directory),
        "processed_pdf_count": processed_pdf_count,
        "failed_pdf_count": len(failed_files),
        "total_article_count": total_article_count,
        "total_chunk_count": total_chunk_count,
        "chroma_db_path": str(chroma_db_path),
        "collection_name": collection_name,
        "all_chunks_jsonl": str(all_chunks_jsonl),
        "failed_files": failed_files,
    }
