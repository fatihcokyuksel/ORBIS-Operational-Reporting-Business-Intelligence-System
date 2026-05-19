from __future__ import annotations

import pandas as pd

from config import settings
from reports.base_agent import BaseReportAgent
from utils.audit_utils import ensure_audit_context
from utils.money_utils import ZERO, calculate_tax_amount, compare_money_values, normalize_tax_rate, round_money, to_decimal
from utils.reporting_utils import build_currency_summary, decimal_series_sum
from utils.validation import (
    ROW_TRACKING_COLUMN,
    derive_period_if_missing,
    ensure_columns,
    ensure_row_tracking,
    is_blank_value,
    isoformat_dates,
    normalize_currency_column,
    normalize_date_columns,
    normalize_numeric_columns,
    normalize_text_columns,
    normalize_timezone_column,
    normalize_transaction_type,
    resolve_duplicate_rows,
)
from utils.warning_utils import append_derived_value_warning, append_dropped_row_warning, append_invalid_value_warning, append_warning_if_mismatch


TRANSACTION_TYPE_ALIASES = {
    "sale": "sale",
    "satis": "sale",
    "purchase": "purchase",
    "alis": "purchase",
    "expense": "expense",
    "gider": "expense",
    "income": "income",
    "gelir": "income",
}

TAX_TYPE_CANONICAL = {
    "kdv": "KDV",
    "stopaj": "Stopaj",
    "gelir vergisi": "Gelir Vergisi",
    "kurumlar vergisi": "Kurumlar Vergisi",
}


class ReportAgent(BaseReportAgent):
    required_fields = ["date", "tax_type", "base_amount", "tax_rate"]
    optional_fields = [
        "tax_amount",
        "invoice_no",
        "counterparty",
        "period",
        "transaction_type",
        "description",
        "currency",
        "timezone",
        "transaction_id",
        "reference_no",
    ]
    numeric_fields = ["base_amount", "tax_rate", "tax_amount"]
    date_fields = ["date"]
    duplicate_subset = ["date", "invoice_no", "tax_type", "base_amount", "tax_amount"]

    def validate(self, df: pd.DataFrame, audit_context: dict | None = None) -> dict:
        context = ensure_audit_context(audit_context, self.report_definition)
        warnings: list[dict] = []
        working_df = ensure_row_tracking(ensure_columns(df, self.all_fields))

        blank_mask = working_df[self.all_fields].apply(lambda series: series.map(is_blank_value)).all(axis=1)
        for _, row in working_df.loc[blank_mask].iterrows():
            append_dropped_row_warning(warnings, row=int(row[ROW_TRACKING_COLUMN]), message="Bos satir temizlendi.", audit_context=context)
        working_df = working_df.loc[~blank_mask].copy()

        working_df = normalize_currency_column(working_df)
        working_df = normalize_timezone_column(working_df)
        working_df = normalize_numeric_columns(working_df, self.numeric_fields)
        working_df = normalize_date_columns(working_df, self.date_fields, warnings=warnings, audit_context=context)
        working_df = normalize_text_columns(working_df, ["tax_type", "invoice_no", "counterparty", "period", "description", "currency", "timezone"])
        working_df["transaction_type"] = working_df["transaction_type"].map(lambda value: normalize_transaction_type(value, TRANSACTION_TYPE_ALIASES))
        working_df["tax_type"] = working_df["tax_type"].map(canonical_tax_type)

        invalid_rows = []
        for index, row in working_df.iterrows():
            normalized_tax_rate = normalize_tax_rate(row.get("tax_rate"))
            if row.get("tax_rate") is not None and normalized_tax_rate is None:
                invalid_rows.append(int(row[ROW_TRACKING_COLUMN]))
                append_invalid_value_warning(
                    warnings,
                    warning_type="invalid_tax_rate",
                    severity="critical",
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field="tax_rate",
                    input_value=row.get("tax_rate"),
                    audit_context=context,
                    action="row_dropped",
                    message="Vergi orani 0-100 araliginda olmali.",
                )
                continue
            tax_amount = calculate_tax_amount(row.get("base_amount"), normalized_tax_rate or ZERO)
            if row.get("tax_amount") is None:
                append_derived_value_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field="tax_amount",
                    calculated_value=round_money(tax_amount),
                    calculated_from=["base_amount", "tax_rate"],
                    audit_context=context,
                    message="Vergi tutari matrah ve oran uzerinden hesaplandi.",
                    lineage={"rule": "base_amount * tax_rate / 100", "source_fields": ["base_amount", "tax_rate"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                )
            elif not compare_money_values(row.get("tax_amount"), tax_amount):
                append_warning_if_mismatch(
                    warnings,
                    field="tax_amount",
                    row=int(row[ROW_TRACKING_COLUMN]),
                    input_value=round_money(row.get("tax_amount")),
                    calculated_value=round_money(tax_amount),
                    calculated_from=["base_amount", "tax_rate"],
                    audit_context=context,
                    message="Input tax_amount ile hesaplanan vergi tutarsizdi. Hesaplanan deger kullanildi.",
                    lineage={"rule": "base_amount * tax_rate / 100", "source_fields": ["base_amount", "tax_rate"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                )
            working_df.at[index, "tax_rate"] = normalized_tax_rate
            working_df.at[index, "tax_amount"] = tax_amount

        for _, row in working_df.iterrows():
            missing_fields = []
            if row.get("date") is pd.NaT or pd.isna(row.get("date")):
                missing_fields.append("date")
            if not row.get("tax_type"):
                missing_fields.append("tax_type")
            if (row.get("base_amount") or ZERO) <= ZERO:
                missing_fields.append("base_amount")
            if row.get("tax_rate") is None:
                missing_fields.append("tax_rate")
            if missing_fields:
                invalid_rows.append(int(row[ROW_TRACKING_COLUMN]))
                append_dropped_row_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field=",".join(missing_fields),
                    message=f"Vergi hesaplama kurallarina uymadigi icin satir atildi: {', '.join(missing_fields)}",
                    audit_context=context,
                    warning_type="missing_required_field",
                )
        if invalid_rows:
            working_df = working_df.loc[~working_df[ROW_TRACKING_COLUMN].isin(invalid_rows)].copy()

        working_df, _ = resolve_duplicate_rows(
            working_df,
            warnings=warnings,
            audit_context=context,
            fallback_subset=self.duplicate_subset,
        )
        working_df = derive_period_if_missing(working_df, date_field="date", period_field="period")

        if working_df.empty:
            return self.finalize_validation_result(
                dataframe=working_df,
                warnings=warnings,
                audit_context=context,
                missing_fields=["date", "tax_type", "base_amount", "tax_rate"],
                message="Vergi hesaplama raporu icin vergi turu, matrah ve oran gereklidir.",
            )

        working_df = isoformat_dates(working_df, self.date_fields)
        return self.finalize_validation_result(dataframe=working_df, warnings=warnings, audit_context=context)

    def generate(self, df: pd.DataFrame, output_path: str | None = None, audit_context: dict | None = None) -> dict:
        working_df = df.copy()
        warnings = list(df.attrs.get("warnings", []))
        audit_context = ensure_audit_context(audit_context or df.attrs.get("audit_context"), self.report_definition)

        currency_summary = build_currency_summary(
            working_df,
            amount_fields=["tax_amount"],
            warnings=warnings,
            audit_context=audit_context,
        )
        summary_group_fields = ["tax_type", "period"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])

        summary_rows = []
        for group_key, group in working_df.groupby(summary_group_fields, dropna=False):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            tax_type = group_key[0]
            period = group_key[1] if len(group_key) > 1 else None
            currency = group_key[2] if len(group_key) > 2 else currency_summary["reporting_currency"]
            summary_rows.append(
                {
                    "Vergi Turu": tax_type,
                    "Donem": period,
                    **({"Para Birimi": currency} if currency_summary["mixed_currency_detected"] else {}),
                    "Matrah Toplami": round_money(decimal_series_sum(group["base_amount"])),
                    "Vergi Tutari Toplami": round_money(decimal_series_sum(group["tax_amount"])),
                    "Islem Sayisi": int(len(group)),
                }
            )
        summary_df = pd.DataFrame(summary_rows)

        detail_rows = working_df.rename(
            columns={
                "date": "Tarih",
                "tax_type": "Vergi Turu",
                "base_amount": "Matrah",
                "tax_rate": "Oran",
                "tax_amount": "Vergi Tutari",
                "transaction_type": "Islem Tipi",
                "description": "Aciklama",
                "currency": "Para Birimi",
            }
        )
        detail_columns = ["Tarih", "Vergi Turu", "Matrah", "Oran", "Vergi Tutari", "Islem Tipi", "Aciklama"]
        if currency_summary["mixed_currency_detected"]:
            detail_columns.append("Para Birimi")
        detail_rows = detail_rows[detail_columns]

        pivot_index = ["period"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])
        pivot = (
            working_df.pivot_table(
                index=pivot_index,
                columns="tax_type",
                values="tax_amount",
                aggfunc=lambda series: sum(series, ZERO),
                fill_value=ZERO,
            )
            .reset_index()
            .rename(columns={"period": "Donem", "currency": "Para Birimi"})
        )
        for column_name in ["KDV", "Stopaj", "Gelir Vergisi", "Kurumlar Vergisi"]:
            if column_name not in pivot.columns:
                pivot[column_name] = 0.0
            else:
                pivot[column_name] = pivot[column_name].map(round_money)
        pivot["Toplam Vergi"] = pivot[["KDV", "Stopaj", "Gelir Vergisi", "Kurumlar Vergisi"]].sum(axis=1)

        total_tax_amount = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df["tax_amount"]))

        return self.build_result(
            df=df,
            warnings=warnings,
            summary={"total_tax_amount": total_tax_amount, **currency_summary},
            tables={
                "summary": summary_df.to_dict(orient="records"),
                "details": detail_rows.to_dict(orient="records"),
                "periodic": pivot.to_dict(orient="records"),
            },
            sheets=[
                {"name": "Vergi Ozeti", "data": summary_df, "currency_columns": ["Matrah Toplami", "Vergi Tutari Toplami"], "number_columns": ["Islem Sayisi"]},
                {"name": "Vergi Detaylari", "data": detail_rows, "currency_columns": ["Matrah", "Vergi Tutari"], "number_columns": ["Oran"], "date_columns": ["Tarih"]},
                {"name": "Donem Bazli Vergi", "data": pivot, "currency_columns": ["KDV", "Stopaj", "Gelir Vergisi", "Kurumlar Vergisi", "Toplam Vergi"]},
            ],
        )


def canonical_tax_type(value) -> str | None:
    if not value:
        return None
    lowered = str(value).lower()
    return TAX_TYPE_CANONICAL.get(lowered, str(value))
