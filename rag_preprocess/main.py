from __future__ import annotations

import argparse
import logging
import sys
import traceback
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

if __package__ in {None, ""}:  # Allows: python rag_preprocess/main.py
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from rag_preprocess.article_chunker import chunk_articles
from rag_preprocess.article_extractor import extract_articles
from rag_preprocess.chroma_indexer import load_embedding_model, save_to_chromadb
from rag_preprocess.config import COLLECTION_NAME, MIN_ARTICLES_FOR_ARTICLE_AWARE, build_output_paths
from rag_preprocess.fallback_chunker import fallback_chunk_pages
from rag_preprocess.gui import ask_directory, show_error, show_info
from rag_preprocess.json_writer import ensure_directories, write_articles_json, write_chunks_jsonl, write_json
from rag_preprocess.law_metadata_extractor import extract_law_metadata
from rag_preprocess.models import Article, Chunk, LawMetadata, PageText
from rag_preprocess.pdf_loader import load_pdf_pages
from rag_preprocess.quality_report import build_global_report, build_quality_report
from rag_preprocess.token_counter import TokenCounter

logger = logging.getLogger(__name__)


def setup_logging(log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process legal PDFs and append embeddings into the shared ChromaDB.")
    parser.add_argument("--input-dir", type=str, default="", help="Directory containing PDF files.")
    return parser.parse_args(argv)


def resolve_selected_dir(args: argparse.Namespace) -> Path | None:
    if args.input_dir:
        return Path(args.input_dir).expanduser().resolve()
    return ask_directory()


def discover_pdf_files(selected_dir: Path) -> list[Path]:
    return sorted(
        selected_dir.glob("*.pdf"),
        key=lambda path: path.name.casefold(),
    )


def process_pdf(
    pdf_path: Path,
    output_paths: dict[str, Path],
    token_counter: TokenCounter,
) -> tuple[LawMetadata, list[Article], list[Chunk], dict[str, Any]]:
    pages: list[PageText] = load_pdf_pages(pdf_path)
    metadata = extract_law_metadata(pdf_path, pages)
    articles = extract_articles(pages, metadata)

    articles_json_path = output_paths["parsed_json"] / f"{pdf_path.stem}_articles.json"
    write_articles_json(articles_json_path, articles)

    if len(articles) >= MIN_ARTICLES_FOR_ARTICLE_AWARE:
        chunks = chunk_articles(articles, token_counter)
    else:
        logger.warning(
            "Yeterli madde bulunamadi, fallback chunker kullanilacak: %s, article_count=%d",
            pdf_path.name,
            len(articles),
        )
        chunks = fallback_chunk_pages(pages, metadata, token_counter)

    per_pdf_chunks_path = output_paths["chunks_jsonl"] / f"{pdf_path.stem}_chunks.jsonl"
    write_chunks_jsonl(per_pdf_chunks_path, chunks)

    quality_report = build_quality_report(
        metadata=metadata,
        articles=articles,
        chunks=chunks,
    )
    quality_report_path = output_paths["quality_reports"] / f"{pdf_path.stem}_quality_report.json"
    write_json(quality_report_path, quality_report)

    return metadata, articles, chunks, quality_report


def run(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = parse_args(argv)
    selected_dir = resolve_selected_dir(args)
    if selected_dir is None:
        print("Klasor secilmedi. Program sonlandirildi.")
        return 0

    output_paths = build_output_paths(selected_dir)
    ensure_directories(
        [
            output_paths["output"],
            output_paths["parsed_json"],
            output_paths["chunks_jsonl"],
            output_paths["quality_reports"],
            output_paths["logs"],
        ]
    )
    log_path = output_paths["logs"] / "process.log"
    setup_logging(log_path)

    logger.info("Secilen klasor: %s", selected_dir)
    pdf_files = discover_pdf_files(selected_dir)
    if not pdf_files:
        message = f"Secilen klasorde PDF bulunamadi:\n{selected_dir}"
        logger.error(message)
        show_error("PDF bulunamadi", message)
        return 1

    try:
        embedding_model = load_embedding_model()
    except Exception as exc:
        message = f"Embedding modeli yuklenemedi:\n{exc}"
        logger.exception(message)
        show_error("Model hatasi", message)
        return 1

    token_counter = TokenCounter(embedding_model=embedding_model)

    all_chunks: list[Chunk] = []
    total_article_count = 0
    processed_pdf_count = 0
    failed_files: list[dict[str, str]] = []

    for pdf_path in pdf_files:
        logger.info("Isleniyor: %s", pdf_path.name)
        try:
            _metadata, articles, chunks, _report = process_pdf(
                pdf_path=pdf_path,
                output_paths=output_paths,
                token_counter=token_counter,
            )
            all_chunks.extend(chunks)
            total_article_count += len(articles)
            processed_pdf_count += 1
            logger.info(
                "PDF tamamlandi: %s, articles=%d, chunks=%d",
                pdf_path.name,
                len(articles),
                len(chunks),
            )
        except Exception as exc:
            logger.exception("PDF islenemedi: %s", pdf_path.name)
            failed_files.append(
                {
                    "source_file": pdf_path.name,
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=5),
                }
            )
            continue

    all_chunks_jsonl = output_paths["chunks_jsonl"] / "all_chunks.jsonl"
    write_chunks_jsonl(all_chunks_jsonl, all_chunks)

    chroma_summary: dict[str, Any] = {}
    try:
        save_to_chromadb(
            chunks=all_chunks,
            chroma_db_path=output_paths["chroma"],
            collection_name=COLLECTION_NAME,
            embedding_model=embedding_model,
        )
        chroma_summary = {
            "collection_name": COLLECTION_NAME,
            "chroma_db_path": str(output_paths["chroma"]),
        }
    except Exception as exc:
        logger.exception("ChromaDB kaydi basarisiz.")
        failed_files.append(
            {
                "source_file": "__chroma_indexing__",
                "error": str(exc),
                "traceback": traceback.format_exc(limit=5),
            }
        )

    global_report = build_global_report(
        selected_directory=selected_dir,
        output_directory=output_paths["output"],
        processed_pdf_count=processed_pdf_count,
        failed_files=failed_files,
        total_article_count=total_article_count,
        total_chunk_count=len(all_chunks),
        chroma_db_path=output_paths["chroma"],
        all_chunks_jsonl=all_chunks_jsonl,
        collection_name=COLLECTION_NAME,
    )
    if chroma_summary:
        global_report["chroma_summary"] = chroma_summary
    write_json(output_paths["quality_reports"] / "global_report.json", global_report)

    summary = (
        f"Islem tamamlandi.\n\n"
        f"Islenen PDF: {processed_pdf_count}\n"
        f"Basarisiz PDF/islem: {len(failed_files)}\n"
        f"Toplam madde: {total_article_count}\n"
        f"Toplam chunk: {len(all_chunks)}\n\n"
        f"ChromaDB: {output_paths['chroma']}\n"
        f"JSONL: {all_chunks_jsonl}\n"
        f"Log: {log_path}"
    )
    logger.info(summary.replace("\n", " | "))
    show_info("RAG preprocessing tamamlandi", summary)
    return 0 if not failed_files else 2


if __name__ == "__main__":
    raise SystemExit(run())
