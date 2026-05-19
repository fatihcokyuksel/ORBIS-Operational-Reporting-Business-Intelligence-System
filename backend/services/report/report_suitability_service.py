from __future__ import annotations

from agents.heuristic_mapping_agent import create_heuristic_mapping
from utils.text_normalization import normalize_text_for_match


def assess_input_support(report_definition: dict, input_type: str, registry_service) -> dict:
    if input_type in report_definition.get("supported_inputs", []):
        return {
            "status": "passed",
            "report_id": report_definition["report_id"],
            "missing_fields": [],
            "warnings": [],
            "available_alternative_reports": [],
            "message": None,
        }

    alternatives = [
        build_report_brief(definition)
        for definition in registry_service.list_reports(input_type=input_type)
        if definition["report_id"] != report_definition["report_id"]
    ]

    return {
        "status": "failed",
        "report_id": report_definition["report_id"],
        "missing_fields": [],
        "warnings": [],
        "available_alternative_reports": alternatives,
        "message": f"Bu rapor {input_type} girisini desteklemiyor.",
    }


def assess_excel_suitability(report_definition: dict, mapping_json: dict, preview_json: dict, registry_service) -> dict:
    required_fields = report_definition["input_contract"]["required_fields"]
    field_mappings = mapping_json.get("field_mappings", {})
    missing_fields = list(mapping_json.get("missing_fields", []))

    for field in required_fields:
        mapping = field_mappings.get(field, {})
        if mapping.get("mapping_type") == "not_available" and field not in missing_fields:
            missing_fields.append(field)

    if mapping_json.get("status") == "passed" and not missing_fields:
        return {
            "status": "passed",
            "report_id": report_definition["report_id"],
            "missing_fields": [],
            "warnings": mapping_json.get("warnings", []),
            "available_alternative_reports": [],
            "message": None,
        }

    alternatives = suggest_alternative_reports_for_excel(
        selected_report_id=report_definition["report_id"],
        preview_json=preview_json,
        registry_service=registry_service,
    )

    return {
        "status": "failed",
        "report_id": report_definition["report_id"],
        "missing_fields": sorted(set(missing_fields)),
        "warnings": mapping_json.get("warnings", []),
        "available_alternative_reports": alternatives,
        "message": mapping_json.get("message") or "Secilen rapor icin gerekli alanlar eksik.",
    }


def assess_prompt_suitability(report_definition: dict, extraction_result: dict, registry_service) -> dict:
    if extraction_result.get("status") == "passed":
        return {
            "status": "passed",
            "report_id": report_definition["report_id"],
            "missing_fields": [],
            "warnings": extraction_result.get("warnings", []),
            "available_alternative_reports": [],
            "message": None,
        }

    alternatives = [
        build_report_brief(definition)
        for definition in registry_service.list_reports(input_type="prompt")
        if definition["report_id"] != report_definition["report_id"]
    ]

    return {
        "status": "failed",
        "report_id": report_definition["report_id"],
        "missing_fields": [],
        "warnings": extraction_result.get("warnings", []),
        "available_alternative_reports": alternatives,
        "message": extraction_result.get("message") or "Prompt verisi secilen rapor icin yeterli degil.",
    }


def suggest_alternative_reports_for_excel(selected_report_id: str, preview_json: dict, registry_service) -> list[dict]:
    alternatives = []
    for definition in registry_service.list_reports(input_type="excel"):
        if definition["report_id"] == selected_report_id:
            continue

        mapping = create_heuristic_mapping(
            report_type=definition["report_id"],
            preview_json=preview_json,
            reason="alternative_check",
        )
        if mapping.get("status") == "passed":
            alternatives.append(build_report_brief(definition))

    return alternatives


def mapping_references_existing_columns(mapping_json: dict, preview_json: dict) -> dict:
    selected_sheet = mapping_json.get("selected_sheet")
    if not selected_sheet:
        return {"valid": False, "errors": ["Mapping selected_sheet icermiyor."]}

    matching_sheet = next(
        (sheet for sheet in preview_json.get("sheets", []) if sheet.get("sheet_name") == selected_sheet),
        None,
    )
    if not matching_sheet:
        return {"valid": False, "errors": [f"Preview icinde selected_sheet bulunamadi: {selected_sheet}"]}

    known_columns = set(matching_sheet.get("columns", []))
    errors = []

    for field_name, mapping in mapping_json.get("field_mappings", {}).items():
        for column_name in mapping.get("source_columns", []):
            if column_name not in known_columns:
                errors.append(f"{field_name}: Preview kolonlari icinde olmayan source_column bulundu: {column_name}")

        source_column = mapping.get("source_column")
        if source_column is not None and source_column not in known_columns:
            errors.append(f"{field_name}: Preview kolonlari icinde olmayan source_column bulundu: {source_column}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


def normalized_payload_is_usable(
    items: list[dict],
    report_definition: dict,
    preview_json: dict | None = None,
    mapping_json: dict | None = None,
) -> bool:
    if not items:
        return False

    input_contract = report_definition.get("input_contract", {})
    required_fields = input_contract.get("required_fields", [])
    if not required_fields:
        return True

    for field in required_fields:
        if all(item.get(field) in [None, ""] for item in items):
            return False

    accepted_directions = set(input_contract.get("accepted_directions", []))
    if "direction" in required_fields and accepted_directions:
        present_directions = {
            item.get("direction")
            for item in items
            if item.get("direction") in accepted_directions
        }
        if not present_directions:
            return False

        if mapping_json and not mapping_has_usable_direction_structure(mapping_json):
            return False

        if preview_json and preview_suggests_bidirectional_data(preview_json, mapping_json, report_definition):
            if len(present_directions) < 2:
                return False

    return True


def build_report_brief(report_definition: dict) -> dict:
    return {
        "report_id": report_definition["report_id"],
        "display_name": report_definition["display_name"],
        "description": report_definition.get("description"),
    }


def mapping_has_usable_direction_structure(mapping_json: dict) -> bool:
    direction_mapping = mapping_json.get("field_mappings", {}).get("direction", {})
    mapping_type = direction_mapping.get("mapping_type")
    rule_type = direction_mapping.get("rule_type")
    source_columns = [column for column in direction_mapping.get("source_columns", []) if column]

    if mapping_type == "not_available":
        return False

    if mapping_type == "derived" and rule_type in {
        "boolean_columns",
        "debit_credit_amount",
        "debit_credit_direction",
    }:
        return len(set(source_columns)) >= 2

    if mapping_type == "derived" and rule_type == "signed_amount_direction":
        return len(source_columns) >= 1

    if mapping_type == "column":
        return bool(direction_mapping.get("source_column"))

    if mapping_type == "constant":
        return bool(direction_mapping.get("default_value"))

    return True


def preview_suggests_bidirectional_data(
    preview_json: dict,
    mapping_json: dict | None,
    report_definition: dict,
) -> bool:
    input_contract = report_definition.get("input_contract", {})
    accepted_directions = input_contract.get("accepted_directions", [])
    if len(accepted_directions) < 2:
        return False

    sheet = find_selected_sheet(preview_json, mapping_json)
    if not sheet:
        return False

    columns = sheet.get("columns", [])
    sample_rows = sheet.get("sample_rows", [])
    if not columns or not sample_rows:
        return False

    left_column, right_column = find_direction_pair(columns, report_definition["report_id"])
    if not left_column or not right_column or left_column == right_column:
        return False

    return column_has_affirmative_samples(left_column, sample_rows) and column_has_affirmative_samples(
        right_column,
        sample_rows,
    )


def find_selected_sheet(preview_json: dict, mapping_json: dict | None) -> dict | None:
    sheets = preview_json.get("sheets", [])
    if not sheets:
        return None

    selected_sheet = mapping_json.get("selected_sheet") if mapping_json else None
    if selected_sheet:
        return next((sheet for sheet in sheets if sheet.get("sheet_name") == selected_sheet), None)
    return sheets[0]


def find_direction_pair(columns: list[str], report_id: str) -> tuple[str | None, str | None]:
    if report_id == "debt_receivable_report":
        left_keywords = ["borc", "debt", "debit", "gider", "expense", "cikti", "cikis"]
        right_keywords = ["alacak", "receivable", "credit", "gelir", "income", "girdi", "giris"]
    else:
        left_keywords = ["gider", "expense", "cikti", "cikis", "borc", "debt", "debit"]
        right_keywords = ["gelir", "income", "girdi", "giris", "alacak", "receivable", "credit"]

    left_column = find_matching_column(columns, left_keywords)
    right_column = find_matching_column(columns, right_keywords)
    return left_column, right_column


def find_matching_column(columns: list[str], keywords: list[str]) -> str | None:
    scored = []
    for column in columns:
        normalized = normalize_text_for_match(column)
        score = 0
        for keyword in keywords:
            if normalized == keyword:
                score += 10
            elif keyword in normalized:
                score += 5
        if score:
            scored.append((score, column))

    if not scored:
        return None
    return sorted(scored, key=lambda item: item[0], reverse=True)[0][1]


def column_has_affirmative_samples(column: str, sample_rows: list[dict]) -> bool:
    yes_values = {"1", "true", "evet", "yes", "x"}
    for row in sample_rows:
        normalized = normalize_text_for_match(row.get(column))
        if normalized in yes_values:
            return True
    return False
