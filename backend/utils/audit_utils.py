from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from config import settings


def create_audit_context(report_definition: dict | None = None) -> dict:
    from utils.date_utils import canonical_now

    return {
        "audit_run_id": uuid4().hex,
        "generated_at": canonical_now().isoformat(),
        "report_version": (report_definition or {}).get("template_version", settings.REPORT_VERSION),
        "calculation_version": settings.CALCULATION_VERSION,
        "timezone": settings.DEFAULT_TIMEZONE,
        "reporting_currency": settings.DEFAULT_CURRENCY,
    }


def ensure_audit_context(audit_context: dict | None, report_definition: dict | None = None) -> dict:
    if audit_context:
        return audit_context
    return create_audit_context(report_definition=report_definition)


def attach_audit_run_id(warnings: list[dict], audit_context: dict | None) -> list[dict]:
    if not audit_context:
        return warnings
    audit_run_id = audit_context.get("audit_run_id")
    if not audit_run_id:
        return warnings
    attached = []
    for warning in warnings:
        payload = dict(warning)
        payload.setdefault("audit_run_id", audit_run_id)
        attached.append(payload)
    return attached


def make_metadata(report_definition: dict, audit_context: dict | None = None) -> dict:
    from utils.date_utils import canonical_now

    context = ensure_audit_context(audit_context, report_definition=report_definition)
    return {
        "audit_run_id": context["audit_run_id"],
        "generated_at": context.get("generated_at") or canonical_now().isoformat(),
        "report_version": context.get("report_version") or report_definition.get("template_version", settings.REPORT_VERSION),
        "calculation_version": context.get("calculation_version") or settings.CALCULATION_VERSION,
        "timezone": context.get("timezone") or settings.DEFAULT_TIMEZONE,
        "reporting_currency": context.get("reporting_currency") or settings.DEFAULT_CURRENCY,
    }
