from __future__ import annotations

from collections import Counter

from config import settings
from utils.audit_utils import attach_audit_run_id


VALID_SEVERITIES = ("info", "warning", "critical", "blocking")


def default_severity_for_type(warning_type: str) -> str:
    mapping = {
        "derived_value": "info",
        "sensitive_data_masked": "info",
        "mismatch": "warning",
        "duplicate": "warning",
        "inconsistent_product_name": "warning",
        "refund_warning": "warning",
        "refund_detected": "info",
        "return_status_detected": "info",
        "unknown_transaction_type": "warning",
        "negative_sale_total": "warning",
        "recalculated_total_sales": "info",
        "invalid_tax_rate": "critical",
        "mixed_currency": "critical",
        "negative_stock": "critical",
        "missing_required_field": "blocking",
        "dropped_row": "blocking",
        "invalid_row_causing_drop": "blocking",
        "filter_field_missing": "warning",
        "filter_no_rows_remaining": "warning",
        "filter_low_confidence": "warning",
        "filter_partially_applied": "warning",
    }
    return mapping.get(warning_type, "warning")


def make_warning(
    warning_type: str,
    message: str,
    *,
    severity: str | None = None,
    row: int | None = None,
    field: str | None = None,
    input_value=None,
    calculated_value=None,
    confidence: str | None = None,
    action: str | None = None,
    audit_context: dict | None = None,
    calculated_from: list[str] | None = None,
    lineage: dict | None = None,
    **extra,
) -> dict:
    payload = {
        "type": warning_type,
        "severity": severity or default_severity_for_type(warning_type),
        "message": message,
        "row": row,
        "field": field,
        "input_value": input_value,
        "calculated_value": calculated_value,
        "confidence": confidence,
        "action": action,
        "audit_run_id": audit_context.get("audit_run_id") if audit_context else None,
        "calculated_from": calculated_from or [],
        "lineage": lineage or {},
    }
    payload.update(extra)
    return payload


def append_warning(warnings: list[dict], warning: dict):
    warnings.append(warning)


def append_warning_if_mismatch(
    warnings: list[dict],
    *,
    field: str,
    row: int | None,
    input_value,
    calculated_value,
    calculated_from: list[str],
    message: str,
    audit_context: dict | None = None,
    severity: str = "warning",
    action: str = "used_calculated_value",
    lineage: dict | None = None,
):
    append_warning(
        warnings,
        make_warning(
            "mismatch",
            message,
            severity=severity,
            row=row,
            field=field,
            input_value=input_value,
            calculated_value=calculated_value,
            action=action,
            audit_context=audit_context,
            calculated_from=calculated_from,
            lineage=lineage,
        ),
    )


def append_invalid_value_warning(
    warnings: list[dict],
    *,
    warning_type: str,
    message: str,
    row: int | None = None,
    field: str | None = None,
    input_value=None,
    severity: str | None = None,
    action: str | None = None,
    audit_context: dict | None = None,
    calculated_from: list[str] | None = None,
    lineage: dict | None = None,
    **extra,
):
    append_warning(
        warnings,
        make_warning(
            warning_type,
            message,
            severity=severity,
            row=row,
            field=field,
            input_value=input_value,
            action=action,
            audit_context=audit_context,
            calculated_from=calculated_from,
            lineage=lineage,
            **extra,
        ),
    )


def append_duplicate_warning(
    warnings: list[dict],
    *,
    row: int | None,
    confidence: str,
    message: str,
    audit_context: dict | None = None,
    action: str = "row_retained",
    severity: str = "warning",
    lineage: dict | None = None,
):
    append_warning(
        warnings,
        make_warning(
            "duplicate",
            message,
            severity=severity,
            row=row,
            confidence=confidence,
            action=action,
            audit_context=audit_context,
            lineage=lineage,
        ),
    )


def append_derived_value_warning(
    warnings: list[dict],
    *,
    row: int | None,
    field: str,
    calculated_value,
    calculated_from: list[str],
    message: str,
    audit_context: dict | None = None,
    lineage: dict | None = None,
):
    append_warning(
        warnings,
        make_warning(
            "derived_value",
            message,
            severity="info",
            row=row,
            field=field,
            calculated_value=calculated_value,
            action="derived_value",
            audit_context=audit_context,
            calculated_from=calculated_from,
            lineage=lineage,
        ),
    )


def append_dropped_row_warning(
    warnings: list[dict],
    *,
    row: int | None,
    message: str,
    field: str | None = None,
    input_value=None,
    audit_context: dict | None = None,
    warning_type: str = "dropped_row",
    severity: str = "blocking",
    lineage: dict | None = None,
):
    append_warning(
        warnings,
        make_warning(
            warning_type,
            message,
            severity=severity,
            row=row,
            field=field,
            input_value=input_value,
            action="row_dropped",
            audit_context=audit_context,
            lineage=lineage,
        ),
    )


def append_negative_stock_warning(
    warnings: list[dict],
    *,
    product: str,
    remaining_stock,
    audit_context: dict | None = None,
    severity: str | None = None,
    row: int | None = None,
):
    append_warning(
        warnings,
        make_warning(
            "negative_stock",
            "Stok cikisi stok girisinden fazla.",
            severity=severity or ("blocking" if settings.STRICT_INVENTORY_VALIDATION else "critical"),
            row=row,
            field="remaining_stock",
            calculated_value=remaining_stock,
            action="used_non_negative_stock_value",
            audit_context=audit_context,
            product=product,
        ),
    )


def unique_warnings(warnings: list[dict], audit_context: dict | None = None) -> list[dict]:
    normalized = []
    for warning in warnings:
        if isinstance(warning, dict):
            normalized.append(warning)
            continue
        normalized.append(
            make_warning(
                "warning",
                str(warning),
                severity="warning",
                action="reported",
                audit_context=audit_context,
            )
        )

    attached = attach_audit_run_id(normalized, audit_context)
    seen = set()
    unique = []
    for warning in attached:
        fingerprint = (
            warning.get("type"),
            warning.get("severity"),
            warning.get("row"),
            warning.get("field"),
            warning.get("message"),
            repr(warning.get("input_value")),
            repr(warning.get("calculated_value")),
            warning.get("action"),
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(warning)
    return unique


def summarize_warning_severity(warnings: list[dict]) -> dict:
    counter = Counter(
        warning.get("severity", "warning") if isinstance(warning, dict) else "warning"
        for warning in warnings
    )
    return {severity: int(counter.get(severity, 0)) for severity in VALID_SEVERITIES}


def determine_execution_status(warnings: list[dict], *, has_partial_sheet: bool = False) -> str:
    severities = {
        warning.get("severity", "warning") if isinstance(warning, dict) else "warning"
        for warning in warnings
    }
    if "blocking" in severities:
        return "failed"
    if has_partial_sheet:
        return "partial"
    if "critical" in severities:
        return "warning"
    return "success"


def legacy_status_from_execution(execution_status: str) -> str:
    if execution_status == "failed":
        return "failed"
    if execution_status in {"warning", "partial"}:
        return "warning"
    return "success"
