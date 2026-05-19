from __future__ import annotations

from datetime import date

import pandas as pd

from services.report.report_registry_service import ReportRegistryService
from utils.date_utils import parse_date_value
from utils.audit_utils import ensure_audit_context
from utils.warning_utils import determine_execution_status, summarize_warning_severity, unique_warnings


STRICT_REQUIRED_FIELDS = ["date", "amount", "description", "direction"]
OPTIONAL_NORMALIZED_FIELDS = ["balance", "counterparty"]

DEFAULT_DIRECTIONS_BY_REPORT = {
    "income_expense_report": {"income", "expense"},
    "cash_flow_report": {"income", "expense"},
    "debt_receivable_report": {"debt", "receivable"},
}

DIRECTION_ALIASES = {
    "income": "income",
    "inflow": "income",
    "gelir": "income",
    "giriÅŸ": "income",
    "giris": "income",
    "girdi": "income",
    "tahsilat": "income",
    "credit": "income",
    "expense": "expense",
    "outflow": "expense",
    "gider": "expense",
    "Ã§Ä±kÄ±ÅŸ": "expense",
    "cikis": "expense",
    "Ã§Ä±ktÄ±": "expense",
    "cikti": "expense",
    "Ã¶deme": "expense",
    "odeme": "expense",
    "debit": "expense",
}


def validate_transactions(
    transactions: list[dict],
    report_type: str | None = None,
    filters: dict | None = None,
    report_definition: dict | None = None,
    audit_context: dict | None = None,
) -> dict:
    context = ensure_audit_context(audit_context, report_definition)
    if report_definition:
        handler_class = ReportRegistryService().resolve_handler_class(report_definition["handler_class"])
        handler = handler_class(report_definition)
        if hasattr(handler, "validate") and not hasattr(handler, "compute"):
            result = handler.validate(pd.DataFrame(transactions), audit_context=context)
            dataframe = result.get("dataframe", pd.DataFrame())
            cleaned_transactions = dataframe.to_dict(orient="records")
            return {
                "valid": result.get("status") != "failed",
                "transactions": cleaned_transactions,
                "usable_row_count": len(cleaned_transactions),
                "dropped_rows": max(len(transactions) - len(cleaned_transactions), 0),
                "errors": [result["message"]] if result.get("status") == "failed" and result.get("message") else [],
                "warnings": result.get("warnings", []),
                "warning_summary": result.get("warning_summary", summarize_warning_severity(result.get("warnings", []))),
                "execution_status": result.get("execution_status"),
                "audit_context": context,
                "metadata": result.get("metadata", {}),
            }

    legacy_result = legacy_validate_transactions(
        transactions=transactions,
        report_type=report_type,
        filters=filters,
        report_definition=report_definition,
    )
    legacy_warnings = unique_warnings(legacy_result.get("warnings", []), context)
    legacy_result["warnings"] = legacy_warnings
    legacy_result["warning_summary"] = summarize_warning_severity(legacy_warnings)
    legacy_result["execution_status"] = determine_execution_status(legacy_warnings)
    legacy_result["audit_context"] = context
    legacy_result["metadata"] = context
    return legacy_result


def legacy_validate_transactions(
    transactions: list[dict],
    report_type: str | None = None,
    filters: dict | None = None,
    report_definition: dict | None = None,
) -> dict:
    errors = []
    warnings = []
    valid_transactions = []

    required_fields = required_fields_for(report_type, report_definition)
    allowed_directions = allowed_directions_for(report_type, report_definition)

    for index, transaction in enumerate(transactions, start=1):
        missing_fields = [
            field
            for field in required_fields
            if transaction.get(field) in [None, ""]
        ]
        if missing_fields:
            warnings.append(
                f"{index}. satÄ±r zorunlu alan eksik olduÄŸu iÃ§in atÄ±ldÄ±: {', '.join(missing_fields)}"
            )
            continue

        amount = parse_amount(transaction.get("amount"))
        if amount is None:
            warnings.append(f"{index}. satÄ±r tutar numerik olmadÄ±ÄŸÄ± iÃ§in atÄ±ldÄ±.")
            continue

        if amount <= 0:
            warnings.append(f"{index}. satÄ±r tutar sÄ±fÄ±r/negatif olduÄŸu iÃ§in atÄ±ldÄ±.")
            continue

        direction = normalize_direction(transaction.get("direction"))
        if allowed_directions and direction not in allowed_directions:
            warnings.append(f"{index}. satÄ±r yÃ¶n deÄŸeri geÃ§ersiz olduÄŸu iÃ§in atÄ±ldÄ±: {transaction.get('direction')}")
            continue

        cleaned = dict(transaction)
        cleaned["amount"] = float(amount)
        cleaned["direction"] = direction
        cleaned["date"] = normalize_date_value(cleaned.get("date"))
        cleaned["description"] = str(cleaned.get("description")).strip()
        for optional_field in OPTIONAL_NORMALIZED_FIELDS:
            cleaned.setdefault(optional_field, None)

        valid_transactions.append(cleaned)

    filtered_transactions = apply_filters(valid_transactions, filters or {})
    if not filtered_transactions:
        errors.append("Filtre ve validation sonrasÄ± rapor Ã¼retecek veri kalmadÄ±.")

    return {
        "valid": len(errors) == 0,
        "transactions": filtered_transactions,
        "usable_row_count": len(filtered_transactions),
        "dropped_rows": len(transactions) - len(filtered_transactions),
        "errors": errors,
        "warnings": warnings,
    }


def required_fields_for(report_type: str | None, report_definition: dict | None) -> list[str]:
    if report_definition:
        configured = report_definition.get("input_contract", {}).get("required_fields", [])
        return list(dict.fromkeys(STRICT_REQUIRED_FIELDS + configured))
    if report_type in {"income_expense_report", "cash_flow_report"}:
        return STRICT_REQUIRED_FIELDS
    if report_type == "debt_receivable_report":
        return ["amount", "direction"]
    return STRICT_REQUIRED_FIELDS


def allowed_directions_for(report_type: str | None, report_definition: dict | None) -> set[str]:
    if report_definition:
        accepted = {
            normalize_direction(direction)
            for direction in report_definition.get("input_contract", {}).get("accepted_directions", [])
        }
        return {direction for direction in accepted if direction}
    return DEFAULT_DIRECTIONS_BY_REPORT.get(report_type, set())


def normalize_direction(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return DIRECTION_ALIASES.get(text, text)


def parse_amount(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_date_value(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def apply_filters(transactions: list[dict], filters: dict) -> list[dict]:
    filtered = transactions
    categories = filters.get("categories") or []
    if categories:
        category_set = {category.lower() for category in categories}
        filtered = [
            item
            for item in filtered
            if str(item.get("category", "")).lower() in category_set
        ]

    date_range = filters.get("date_range") or {}
    start = date_range.get("start")
    end = date_range.get("end")
    if start or end:
        filtered = [
            item
            for item in filtered
            if date_in_range(item.get("date"), start=start, end=end)
        ]

    return filtered


def date_in_range(value: str | None, start: str | None, end: str | None) -> bool:
    if not value:
        return False

    try:
        current_parsed = parse_date_value(value, timezone_value=None)
        if current_parsed is None or pd.isna(current_parsed):
            return False
        current = current_parsed.date()
        start_date = date.fromisoformat(start) if start else None
        end_date = date.fromisoformat(end) if end else None
    except ValueError:
        return False

    if start_date and current < start_date:
        return False
    if end_date and current > end_date:
        return False
    return True
