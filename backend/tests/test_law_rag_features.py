from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from law_rag.config import RagSettings
from law_rag.duplicate_checker import filter_duplicate_chunks
from law_rag.embedding_pipeline import standardize_chunks
from law_rag.query_parser import parse_law_article_query
from law_rag.retrieval import retrieve_law_article
from rag_preprocess.models import Chunk


class FakeCollection:
    def __init__(self, records: list[dict] | None = None):
        self.records = list(records or [])

    def get(self, ids=None, where=None, include=None, limit=None, offset=None):
        del include, limit, offset
        rows = list(self.records)
        if ids is not None:
            rows = [row for row in rows if row["id"] in set(ids)]
        if where is not None:
            rows = [row for row in rows if _matches_where(row["metadata"], where)]
        return {
            "ids": [row["id"] for row in rows],
            "documents": [row["document"] for row in rows],
            "metadatas": [row["metadata"] for row in rows],
        }


def _matches_where(metadata: dict, where: dict) -> bool:
    if "$and" in where:
        return all(_matches_where(metadata, item) for item in where["$and"])
    return all(str(metadata.get(key) or "") == str(value) for key, value in where.items())


def build_settings() -> RagSettings:
    return RagSettings(
        project_root=Path(".").resolve(),
        chroma_db_path=Path("chroma_local_kanun_db").resolve(),
        chroma_collection_name="kanun_embedding",
        embedding_model_name="BAAI/bge-m3",
        embedding_batch_size=2,
        chroma_add_batch_size=2,
        max_model_tokens=8192,
        migration_backup_dir=Path("storage/chroma_backups").resolve(),
        language="tr",
        law_aliases={
            "VUK": "Vergi Usul Kanunu",
            "VERGI USUL KANUNU": "Vergi Usul Kanunu",
            "KVKK": "Kisisel Verilerin Korunmasi Kanunu",
        },
    )


def test_standardize_chunks_preserves_old_fields_and_adds_new_metadata():
    settings = build_settings()
    chunk = Chunk(
        id="193_2",
        text="Gelir Vergisi Kanunu Madde 2 - Gelire giren kazanc ve iratlar...",
        metadata={
            "source": "193.pdf",
            "page": 1,
            "type": "NarrativeText",
            "law_no": "193",
            "law_name": "Gelir Vergisi Kanunu",
            "article_no": "2",
            "chunk_index": 1,
        },
    )

    standardized = standardize_chunks([chunk], settings)[0]

    assert standardized.metadata["source"] == "193.pdf"
    assert standardized.metadata["kanun_no"] == "193"
    assert standardized.metadata["kanun_adi"] == "Gelir Vergisi Kanunu"
    assert standardized.metadata["kanun_adi_normalized"] == "GELIR VERGISI KANUNU"
    assert standardized.metadata["madde_no"] == "2"
    assert standardized.metadata["language"] == "tr"
    assert standardized.metadata["content_hash"]


def test_duplicate_checker_skips_existing_id_and_hash():
    existing = FakeCollection(
        [
            {
                "id": "chunk-1",
                "document": "Madde 1",
                "metadata": {"content_hash": "hash-1"},
            }
        ]
    )
    chunks = [
        Chunk(id="chunk-1", text="Madde 1", metadata={"content_hash": "hash-1"}),
        Chunk(id="chunk-2", text="Madde 1 duplicate", metadata={"content_hash": "hash-1"}),
        Chunk(id="chunk-3", text="Madde 2", metadata={"content_hash": "hash-2"}),
    ]

    result = filter_duplicate_chunks(existing, chunks, batch_size=2)

    assert [chunk.id for chunk in result.new_chunks] == ["chunk-3"]
    assert result.skipped_by_id == 1
    assert result.skipped_by_hash == 1


def test_parse_law_article_query_supports_aliases_and_numbered_laws():
    settings = build_settings()

    parsed_alias = parse_law_article_query("VUK 359. maddeyi getir", settings.law_aliases)
    assert parsed_alias is not None
    assert parsed_alias.article_no == "359"
    assert parsed_alias.normalized_law_name == "VERGI USUL KANUNU"

    parsed_numbered = parse_law_article_query("6102 sayili kanunun 64. maddesi", settings.law_aliases)
    assert parsed_numbered is not None
    assert parsed_numbered.law_no == "6102"
    assert parsed_numbered.article_no == "64"


def test_retrieve_law_article_prefers_exact_metadata_match():
    parsed = parse_law_article_query("KVKK madde 11", build_settings().law_aliases)
    assert parsed is not None

    collection = FakeCollection(
        [
            {
                "id": "a",
                "document": "Birinci belge",
                "metadata": {
                    "kanun_adi_normalized": "KISISEL VERILERIN KORUNMASI KANUNU",
                    "madde_no": "11",
                    "page": 3,
                    "chunk_index": 1,
                },
            },
            {
                "id": "b",
                "document": "Ikinci belge",
                "metadata": {
                    "kanun_adi_normalized": "KISISEL VERILERIN KORUNMASI KANUNU",
                    "madde_no": "11",
                    "page": 4,
                    "chunk_index": 2,
                },
            },
        ]
    )

    result = retrieve_law_article(collection, parsed)

    assert result["strategy"] == "exact_metadata"
    assert [row["id"] for row in result["rows"]] == ["a", "b"]
    assert "Birinci belge" in result["combined_text"]
