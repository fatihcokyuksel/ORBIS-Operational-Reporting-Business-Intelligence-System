from __future__ import annotations

from services.report.report_registry_service import ReportRegistryService
from utils.mapping_utils import (
    FIELD_ALIASES,
    column_mapping,
    constant_mapping,
    derived_mapping,
    empty_mapping,
    fields_for_report,
    match_field_by_alias,
)
from utils.text_normalization import normalize_text_for_match


INCOME_EXPENSE_LEFT_KEYWORDS = ["gider", "expense", "cikis", "debit", "outflow"]
INCOME_EXPENSE_RIGHT_KEYWORDS = ["gelir", "income", "giris", "credit", "inflow"]
DEBT_RECEIVABLE_LEFT_KEYWORDS = ["borc", "debt", "debit", "gider", "cikis"]
DEBT_RECEIVABLE_RIGHT_KEYWORDS = ["alacak", "receivable", "credit", "gelir", "giris"]


def create_heuristic_mapping(report_type: str, preview_json: dict, reason: str | None = None) -> dict:
    registry = ReportRegistryService()
    report_definition = registry.get_report_definition(report_type)
    selected_sheet = choose_best_sheet(preview_json, report_definition)
    fields = fields_for_report(report_definition)

    if not selected_sheet:
        return failed_mapping(report_type, fields, ["sheet"], "Excel icinde okunabilir sheet bulunamadi.", reason)

    columns = selected_sheet.get("columns", [])
    numeric_columns = set(selected_sheet.get("numeric_columns", []))
    sample_rows = selected_sheet.get("sample_rows", [])

    field_mappings = {}
    left_keywords, right_keywords = direction_keywords(report_definition)
    left_column = find_matching_column(columns, left_keywords)
    right_column = find_matching_column(columns, right_keywords)

    for field_name in fields:
        direct_column = find_best_column(columns, FIELD_ALIASES.get(field_name, []))

        if field_name == "amount":
            field_mappings[field_name] = build_amount_mapping(
                field_name=field_name,
                direct_column=direct_column,
                left_column=left_column,
                right_column=right_column,
                numeric_columns=numeric_columns,
            )
            continue

        if field_name in {"direction", "transaction_direction"}:
            field_mappings[field_name] = build_direction_mapping(
                field_name=field_name,
                direct_column=direct_column,
                left_column=left_column,
                right_column=right_column,
                amount_mapping=field_mappings.get("amount"),
                sample_rows=sample_rows,
            )
            continue

        if field_name == "category" and not direct_column:
            description_column = find_best_column(columns, FIELD_ALIASES.get("description", []))
            if description_column:
                field_mappings[field_name] = {
                    "mapping_type": "llm_infer_later",
                    "source_column": None,
                    "source_columns": [description_column],
                    "rule_type": "none",
                    "output_type": "string",
                    "default_value": None,
                }
                continue

        if field_name == "customer" and not direct_column:
            direct_column = find_best_column(columns, FIELD_ALIASES.get("counterparty", []))

        if field_name == "counterparty" and not direct_column:
            direct_column = find_best_column(columns, FIELD_ALIASES.get("customer", []))

        if field_name == "currency" and not direct_column:
            field_mappings[field_name] = constant_mapping(field_name, "TRY")
            continue

        field_mappings[field_name] = column_mapping(field_name, direct_column)

    missing_fields = required_missing_fields(report_definition, field_mappings)
    warnings = []
    if reason:
        warnings.append(f"LLM mapping kullanilamadi, heuristic mapping devrede: {reason}")
    if missing_fields:
        warnings.append("Bazi zorunlu alanlar heuristik esleme ile bulunamadi.")

    return {
        "status": "failed" if missing_fields else "passed",
        "report_type": report_type,
        "selected_sheet": selected_sheet.get("sheet_name") if not missing_fields else None,
        "confidence": 0.75 if not missing_fields else 0.35,
        "missing_fields": missing_fields,
        "field_mappings": field_mappings,
        "warnings": warnings,
        "message": None if not missing_fields else "Heuristic mapping zorunlu alanlari bulamadi.",
    }


def choose_best_sheet(preview_json: dict, report_definition: dict) -> dict | None:
    sheets = preview_json.get("sheets", [])
    if not sheets:
        return None

    candidate_fields = fields_for_report(report_definition)

    def score(sheet):
        columns = sheet.get("columns", [])
        field_hits = 0
        for column in columns:
            if match_field_by_alias(column, candidate_fields):
                field_hits += 1
        return field_hits * 10 + sheet.get("row_count", 0) + sheet.get("column_count", 0)

    return max(sheets, key=score)


def find_best_column(columns: list[str], aliases: list[str]) -> str | None:
    best_match = None
    best_score = 0
    for column in columns:
        normalized_column = normalize_text_for_match(column)
        for alias in aliases:
            normalized_alias = normalize_text_for_match(alias)
            score = 0
            if normalized_column == normalized_alias:
                score = 10
            elif normalized_alias and normalized_alias in normalized_column:
                score = 5
            if score > best_score:
                best_score = score
                best_match = column
    return best_match


def find_matching_column(columns: list[str], keywords: list[str]) -> str | None:
    return find_best_column(columns, keywords)


def build_amount_mapping(
    field_name: str,
    direct_column: str | None,
    left_column: str | None,
    right_column: str | None,
    numeric_columns: set[str],
) -> dict:
    if direct_column:
        return column_mapping(field_name, direct_column)
    if left_column and right_column and left_column != right_column:
        return derived_mapping(field_name, [left_column, right_column], "debit_credit_amount")
    candidate_numeric = [column for column in numeric_columns if column not in {left_column, right_column}]
    if candidate_numeric:
        return column_mapping(field_name, candidate_numeric[0])
    return empty_mapping(field_name)


def build_direction_mapping(
    field_name: str,
    direct_column: str | None,
    left_column: str | None,
    right_column: str | None,
    amount_mapping: dict | None,
    sample_rows: list[dict],
) -> dict:
    if direct_column:
        return column_mapping(field_name, direct_column)

    if left_column and right_column and left_column != right_column:
        if is_boolean_indicator_pair(left_column, right_column, sample_rows):
            return derived_mapping(field_name, [left_column, right_column], "boolean_columns")
        return derived_mapping(field_name, [left_column, right_column], "debit_credit_direction")

    if amount_mapping and amount_mapping.get("mapping_type") == "column":
        amount_column = amount_mapping.get("source_column")
        if amount_column:
            return derived_mapping(field_name, [amount_column], "signed_amount_direction")

    return empty_mapping(field_name)


def is_boolean_indicator_pair(left_column: str, right_column: str, sample_rows: list[dict]) -> bool:
    if not sample_rows:
        return False

    allowed_values = {"1", "0", "true", "false", "evet", "hayir", "yes", "no", "x", ""}
    seen_values = []
    for row in sample_rows:
        for column in [left_column, right_column]:
            value = normalize_text_for_match(row.get(column))
            if value:
                seen_values.append(value)
    if not seen_values:
        return False
    return all(value in allowed_values for value in seen_values)


def required_missing_fields(report_definition: dict, field_mappings: dict) -> list[str]:
    required_fields = report_definition.get("input_contract", {}).get("required_fields", [])
    missing = []
    for field_name in required_fields:
        mapping = field_mappings.get(field_name, empty_mapping(field_name))
        if mapping.get("mapping_type") == "not_available":
            missing.append(field_name)
    return missing


def failed_mapping(report_type: str, fields: list[str], missing_fields: list[str], message: str, reason: str | None):
    field_mappings = {field_name: empty_mapping(field_name) for field_name in fields}
    warnings = [reason] if reason else []
    return {
        "status": "failed",
        "report_type": report_type,
        "selected_sheet": None,
        "confidence": 0.0,
        "missing_fields": missing_fields,
        "field_mappings": field_mappings,
        "warnings": warnings,
        "message": message,
    }


def direction_keywords(report_definition: dict) -> tuple[list[str], list[str]]:
    accepted = set(report_definition.get("input_contract", {}).get("accepted_directions", []))
    if {"debt", "receivable"} & accepted or "transaction_direction" in fields_for_report(report_definition):
        return DEBT_RECEIVABLE_LEFT_KEYWORDS, DEBT_RECEIVABLE_RIGHT_KEYWORDS
    return INCOME_EXPENSE_LEFT_KEYWORDS, INCOME_EXPENSE_RIGHT_KEYWORDS
