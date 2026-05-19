from __future__ import annotations

from typing import Any

from law_rag.query_parser import LawArticleQuery


def _flatten_get_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    ids = result.get("ids") or []
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    rows: list[dict[str, Any]] = []
    for index, item_id in enumerate(ids):
        rows.append(
            {
                "id": item_id,
                "document": documents[index] if index < len(documents) else "",
                "metadata": metadatas[index] if index < len(metadatas) else {},
            }
        )
    return rows


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        rows,
        key=lambda row: (
            int(row["metadata"].get("page") or row["metadata"].get("page_start") or 0),
            int(row["metadata"].get("chunk_index") or 0),
            int(row["metadata"].get("article_part") or 0),
        ),
    )


def _query_exact_article(collection: Any, parsed_query: LawArticleQuery) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    if parsed_query.law_no:
        result = collection.get(
            where={"$and": [{"kanun_no": parsed_query.law_no}, {"madde_no": parsed_query.article_no}]},
            include=["documents", "metadatas"],
        )
        rows.extend(_flatten_get_result(result))

    if rows:
        return _sort_rows(rows)

    if parsed_query.normalized_law_name:
        result = collection.get(
            where={"$and": [{"kanun_adi_normalized": parsed_query.normalized_law_name}, {"madde_no": parsed_query.article_no}]},
            include=["documents", "metadatas"],
        )
        rows.extend(_flatten_get_result(result))
    return _sort_rows(rows)


def _query_metadata_fallback(collection: Any, parsed_query: LawArticleQuery) -> list[dict[str, Any]]:
    candidate_rows: list[dict[str, Any]] = []
    if parsed_query.law_no:
        candidate_rows.extend(
            _flatten_get_result(
                collection.get(
                    where={"kanun_no": parsed_query.law_no},
                    include=["documents", "metadatas"],
                )
            )
        )
    if parsed_query.normalized_law_name:
        candidate_rows.extend(
            _flatten_get_result(
                collection.get(
                    where={"kanun_adi_normalized": parsed_query.normalized_law_name},
                    include=["documents", "metadatas"],
                )
            )
        )

    filtered = [
        row
        for row in candidate_rows
        if str(row["metadata"].get("madde_no") or row["metadata"].get("article_no") or "") == parsed_query.article_no
        or f"|{parsed_query.article_no}|" in str(row["metadata"].get("included_articles_padded") or "")
    ]
    unique = {row["id"]: row for row in filtered}
    return _sort_rows(list(unique.values()))


def retrieve_law_article(collection: Any, parsed_query: LawArticleQuery) -> dict[str, Any]:
    rows = _query_exact_article(collection, parsed_query)
    strategy = "exact_metadata"

    if not rows:
        rows = _query_metadata_fallback(collection, parsed_query)
        strategy = "metadata_filter"

    return {
        "strategy": strategy,
        "rows": rows,
        "combined_text": "\n\n".join(row["document"] for row in rows if row["document"]),
    }
