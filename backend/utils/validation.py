from __future__ import annotations

import pandas as pd

from config import settings
from utils.date_utils import parse_date_value, to_period_string
from utils.money_utils import normalize_currency, to_decimal
from utils.warning_utils import append_duplicate_warning


PAID_STATUSES = {"paid", "odendi", "odenmis", "closed", "kapandi"}
UNPAID_STATUSES = {"unpaid", "odenmedi", "acik", "open"}
PARTIAL_STATUSES = {"partial", "partially_paid", "kismi", "kismen_odendi"}
ROW_TRACKING_COLUMN = "__row_num__"


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    working_df = df.copy()
    for column in columns:
        if column not in working_df.columns:
            working_df[column] = pd.NA
    return working_df


def ensure_row_tracking(df: pd.DataFrame) -> pd.DataFrame:
    working_df = df.copy()
    if ROW_TRACKING_COLUMN not in working_df.columns:
        working_df[ROW_TRACKING_COLUMN] = range(1, len(working_df) + 1)
    return working_df


def normalize_text_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    working_df = df.copy()
    for column in columns:
        if column not in working_df.columns:
            continue
        working_df[column] = working_df[column].map(clean_text)
    return working_df


def normalize_numeric_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    working_df = df.copy()
    for column in columns:
        if column not in working_df.columns:
            continue
        working_df[column] = working_df[column].map(to_decimal)
    return working_df


def normalize_currency_column(df: pd.DataFrame, column: str = "currency") -> pd.DataFrame:
    working_df = df.copy()
    if column not in working_df.columns:
        working_df[column] = settings.DEFAULT_CURRENCY
        return working_df
    working_df[column] = working_df[column].map(lambda value: normalize_currency(value, settings.DEFAULT_CURRENCY))
    return working_df


def normalize_timezone_column(df: pd.DataFrame, column: str = "timezone") -> pd.DataFrame:
    working_df = df.copy()
    if column not in working_df.columns:
        working_df[column] = settings.DEFAULT_TIMEZONE
        return working_df
    working_df[column] = working_df[column].map(clean_text).fillna(settings.DEFAULT_TIMEZONE)
    return working_df


def normalize_date_columns(
    df: pd.DataFrame,
    columns: list[str],
    *,
    timezone_field: str | None = "timezone",
    warnings: list[dict] | None = None,
    audit_context: dict | None = None,
) -> pd.DataFrame:
    working_df = df.copy()
    for column in columns:
        if column not in working_df.columns:
            continue
        if working_df.empty:
            working_df[column] = pd.Series(dtype="object")
            continue

        column_source = working_df[column]
        column_values = column_source.iloc[:, 0] if isinstance(column_source, pd.DataFrame) else column_source
        row_numbers = working_df[ROW_TRACKING_COLUMN] if ROW_TRACKING_COLUMN in working_df.columns else pd.Series([None] * len(working_df), index=working_df.index)

        if timezone_field and timezone_field in working_df.columns:
            timezone_source = working_df[timezone_field]
            timezone_values = timezone_source.iloc[:, 0] if isinstance(timezone_source, pd.DataFrame) else timezone_source
            working_df[column] = [
                parse_date_value(
                    value,
                    timezone_value=timezone_value,
                    warnings=warnings,
                    row=int(row_number) if row_number is not None and not pd.isna(row_number) else None,
                    audit_context=audit_context,
                )
                for value, timezone_value, row_number in zip(column_values.tolist(), timezone_values.tolist(), row_numbers.tolist())
            ]
        else:
            working_df[column] = [
                parse_date_value(
                    value,
                    warnings=warnings,
                    row=int(row_number) if row_number is not None and not pd.isna(row_number) else None,
                    audit_context=audit_context,
                )
                for value, row_number in zip(column_values.tolist(), row_numbers.tolist())
            ]
    return working_df


def drop_blank_rows(df: pd.DataFrame, fields: list[str]) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df.copy(), 0

    relevant = [field for field in fields if field in df.columns]
    if not relevant:
        return df.copy(), 0

    blank_mask = df[relevant].apply(lambda series: series.map(is_blank_value)).all(axis=1)
    dropped = int(blank_mask.sum())
    return df.loc[~blank_mask].copy(), dropped


def drop_missing_required_rows(df: pd.DataFrame, required_fields: list[str]) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df.copy(), 0

    relevant = [field for field in required_fields if field in df.columns]
    if not relevant:
        return df.copy(), 0

    missing_mask = df[relevant].apply(lambda series: series.map(is_blank_value)).any(axis=1)
    dropped = int(missing_mask.sum())
    return df.loc[~missing_mask].copy(), dropped


def resolve_duplicate_rows(
    df: pd.DataFrame,
    *,
    warnings: list[dict],
    audit_context: dict | None = None,
    fallback_subset: list[str] | None = None,
) -> tuple[pd.DataFrame, int]:
    if df.empty:
        return df.copy(), 0

    working_df = df.copy()
    dropped_total = 0

    transaction_id_fields = [field for field in ["transaction_id"] if field in working_df.columns]
    for field in transaction_id_fields:
        mask = working_df[field].notna() & working_df[field].astype(str).str.strip().ne("")
        duplicates = working_df.loc[mask & working_df.duplicated(subset=[field], keep="first")]
        for _, row in duplicates.iterrows():
            append_duplicate_warning(
                warnings,
                row=int(row.get(ROW_TRACKING_COLUMN)),
                confidence="high",
                message=f"{field} bazli duplicate kayit kaldirildi.",
                audit_context=audit_context,
                action="row_dropped",
                severity="warning",
                lineage={"rule": "duplicate_exact_match", "source_fields": [field], "config_snapshot": {}},
            )
        if bool(mask.any()):
            before = len(working_df)
            deduped_masked = working_df.loc[mask].drop_duplicates(subset=[field], keep="first")
            working_df = pd.concat([deduped_masked, working_df.loc[~mask]], ignore_index=True).sort_values(ROW_TRACKING_COLUMN)
            dropped_total += before - len(working_df)

    if {"invoice_no", "counterparty"} <= set(working_df.columns):
        invoice_mask = (
            working_df["invoice_no"].notna()
            & working_df["counterparty"].notna()
            & working_df["invoice_no"].astype(str).str.strip().ne("")
        )
        duplicates = working_df.loc[invoice_mask & working_df.duplicated(subset=["invoice_no", "counterparty"], keep="first")]
        for _, row in duplicates.iterrows():
            append_duplicate_warning(
                warnings,
                row=int(row.get(ROW_TRACKING_COLUMN)),
                confidence="high",
                message="Ayni invoice_no ve cari kombinasyonu duplicate olarak kaldirildi.",
                audit_context=audit_context,
                action="row_dropped",
                severity="warning",
                lineage={"rule": "duplicate_invoice_counterparty", "source_fields": ["invoice_no", "counterparty"], "config_snapshot": {}},
            )
        if bool(invoice_mask.any()):
            before = len(working_df)
            deduped_masked = working_df.loc[invoice_mask].drop_duplicates(subset=["invoice_no", "counterparty"], keep="first")
            working_df = pd.concat([deduped_masked, working_df.loc[~invoice_mask]], ignore_index=True).sort_values(ROW_TRACKING_COLUMN)
            dropped_total += before - len(working_df)

    valid_subset = [field for field in (fallback_subset or []) if field in working_df.columns]
    if valid_subset:
        low_confidence_rows = working_df.loc[working_df.duplicated(subset=valid_subset, keep=False)]
        emitted_rows = set()
        for _, row in low_confidence_rows.iterrows():
            row_number = int(row.get(ROW_TRACKING_COLUMN))
            if row_number in emitted_rows:
                continue
            emitted_rows.add(row_number)
            append_duplicate_warning(
                warnings,
                row=row_number,
                confidence="low",
                message="Benzer transaction bulundu fakat otomatik silinmedi.",
                audit_context=audit_context,
                action="row_retained",
                severity="warning",
                lineage={"rule": "duplicate_fallback_similarity", "source_fields": valid_subset, "config_snapshot": {}},
            )

    return working_df.copy(), dropped_total


def clean_text(value) -> str | None:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def is_blank_value(value) -> bool:
    if value is None or value is pd.NA:
        return True
    if isinstance(value, str):
        return not value.strip()
    return bool(pd.isna(value))


def normalize_payment_status(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    lowered = text.lower()
    if lowered in PAID_STATUSES:
        return "paid"
    if lowered in UNPAID_STATUSES:
        return "unpaid"
    if lowered in PARTIAL_STATUSES:
        return "partial"
    return lowered


def normalize_income_expense_direction(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    lowered = text.lower()
    aliases = {
        "income": "income",
        "inflow": "income",
        "gelir": "income",
        "giris": "income",
        "tahsilat": "income",
        "sale": "income",
        "sales": "income",
        "expense": "expense",
        "outflow": "expense",
        "gider": "expense",
        "cikis": "expense",
        "odeme": "expense",
        "purchase": "expense",
    }
    return aliases.get(lowered, lowered)


def normalize_debt_receivable_direction(value) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    lowered = text.lower()
    aliases = {
        "receivable": "receivable",
        "alacak": "receivable",
        "income": "receivable",
        "credit": "receivable",
        "customer": "receivable",
        "debt": "debt",
        "borc": "debt",
        "expense": "debt",
        "debit": "debt",
        "payable": "debt",
        "supplier": "debt",
    }
    return aliases.get(lowered, lowered)


def normalize_transaction_type(value, allowed: dict[str, str] | None = None) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    lowered = text.lower()
    if allowed:
        return allowed.get(lowered, lowered)
    return lowered


def isoformat_dates(df: pd.DataFrame, date_fields: list[str]) -> pd.DataFrame:
    working_df = df.copy()
    for field in date_fields:
        if field not in working_df.columns:
            continue
        working_df[field] = working_df[field].map(
            lambda value: value.isoformat() if isinstance(value, pd.Timestamp) and not pd.isna(value) else None
        )
    return working_df


def derive_period_if_missing(
    df: pd.DataFrame,
    date_field: str = "date",
    period_field: str = "period",
    timezone_field: str | None = "timezone",
) -> pd.DataFrame:
    working_df = df.copy()
    if period_field not in working_df.columns:
        working_df[period_field] = pd.NA
    if date_field in working_df.columns:
        missing_period_mask = working_df[period_field].isna() | (working_df[period_field].astype(str).str.strip() == "")
        working_df.loc[missing_period_mask, period_field] = working_df.loc[missing_period_mask].apply(
            lambda row: to_period_string(
                row[date_field],
                timezone_value=row.get(timezone_field) if timezone_field and timezone_field in working_df.columns else None,
            ),
            axis=1,
        )
    return working_df


def attach_validation_metadata(
    df: pd.DataFrame,
    *,
    warnings: list[dict],
    audit_context: dict | None = None,
) -> pd.DataFrame:
    working_df = df.copy()
    working_df.attrs["warnings"] = warnings
    if audit_context:
        working_df.attrs["audit_context"] = audit_context
    return working_df
