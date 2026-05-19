from __future__ import annotations

from datetime import date, datetime
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd

from config import settings
from utils.warning_utils import append_invalid_value_warning


def normalize_timezone(
    timezone_value: str | None = None,
    *,
    warnings: list[dict] | None = None,
    row: int | None = None,
    audit_context: dict | None = None,
) -> ZoneInfo:
    candidate = (timezone_value or settings.DEFAULT_TIMEZONE or "Europe/Istanbul").strip()
    try:
        return ZoneInfo(candidate)
    except ZoneInfoNotFoundError:
        if warnings is not None:
            append_invalid_value_warning(
                warnings,
                warning_type="invalid_timezone",
                severity="warning",
                row=row,
                input_value=timezone_value,
                field="timezone",
                action="used_default_timezone",
                audit_context=audit_context,
                message="Timezone taninamadi. Default timezone kullanildi.",
            )
        return ZoneInfo(settings.DEFAULT_TIMEZONE)


def localize_naive_datetime(value: pd.Timestamp, timezone: ZoneInfo) -> pd.Timestamp:
    if pd.isna(value):
        return value
    if value.tzinfo is None:
        return value.tz_localize(timezone)
    return value


def convert_to_canonical_timezone(value: pd.Timestamp, timezone: ZoneInfo | None = None) -> pd.Timestamp:
    if pd.isna(value):
        return value
    source_timezone = timezone or normalize_timezone()
    canonical_timezone = normalize_timezone(settings.DEFAULT_TIMEZONE)
    localized = localize_naive_datetime(value, source_timezone)
    return localized.tz_convert(canonical_timezone)


def parse_date_value(
    value,
    *,
    timezone_value: str | None = None,
    warnings: list[dict] | None = None,
    row: int | None = None,
    audit_context: dict | None = None,
):
    if value in [None, ""]:
        return pd.NaT

    source_timezone = normalize_timezone(
        timezone_value,
        warnings=warnings,
        row=row,
        audit_context=audit_context,
    )

    text = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}($|\s|T)", text):
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=False)
    else:
        parsed = pd.to_datetime(value, errors="coerce", dayfirst=True, utc=False)

    if pd.isna(parsed):
        return pd.NaT

    if not isinstance(parsed, pd.Timestamp):
        parsed = pd.Timestamp(parsed)
    return convert_to_canonical_timezone(parsed, source_timezone)


def derive_period_from_timezone_aware_datetime(value, timezone_value: str | None = None) -> str | None:
    parsed = parse_date_value(value, timezone_value=timezone_value)
    if pd.isna(parsed):
        return None
    return parsed.strftime("%Y-%m")


def to_iso_date(value, timezone_value: str | None = None) -> str | None:
    parsed = parse_date_value(value, timezone_value=timezone_value)
    if pd.isna(parsed):
        return None
    return parsed.isoformat()


def to_period_string(value, timezone_value: str | None = None) -> str | None:
    return derive_period_from_timezone_aware_datetime(value, timezone_value=timezone_value)


def canonical_now(timezone_value: str | None = None) -> datetime:
    timezone = normalize_timezone(timezone_value)
    return datetime.now(timezone)


def today_date(timezone_value: str | None = None) -> date:
    return canonical_now(timezone_value).date()


def overdue_days(value, reference_date: date | None = None, timezone_value: str | None = None) -> int | None:
    parsed = parse_date_value(value, timezone_value=timezone_value)
    if pd.isna(parsed):
        return None
    reference = reference_date or today_date(timezone_value)
    return (reference - parsed.date()).days


def is_overdue(value, reference_date: date | None = None, timezone_value: str | None = None) -> bool:
    days = overdue_days(value, reference_date=reference_date, timezone_value=timezone_value)
    return days is not None and days > 0
