from __future__ import annotations

import pandas as pd

from reports.base_agent import BaseReportAgent
from utils.audit_utils import ensure_audit_context
from utils.date_utils import overdue_days, today_date
from utils.money_utils import ZERO, round_money, to_decimal
from utils.reporting_utils import build_currency_summary, decimal_series_sum
from utils.validation import (
    ROW_TRACKING_COLUMN,
    ensure_columns,
    ensure_row_tracking,
    is_blank_value,
    isoformat_dates,
    normalize_currency_column,
    normalize_date_columns,
    normalize_debt_receivable_direction,
    normalize_numeric_columns,
    normalize_payment_status,
    normalize_text_columns,
    normalize_timezone_column,
    resolve_duplicate_rows,
)
from utils.warning_utils import append_dropped_row_warning


COUNTERPARTY_TYPE_ALIASES = {
    "customer": "customer",
    "musteri": "customer",
    "müşteri": "customer",
    "tedarikci": "supplier",
    "tedarikçi": "supplier",
    "supplier": "supplier",
    "vendor": "supplier",
}


class ReportAgent(BaseReportAgent):
    required_fields = ["date", "counterparty", "amount", "transaction_direction"]
    optional_fields = [
        "counterparty_type",
        "due_date",
        "payment_status",
        "description",
        "invoice_no",
        "currency",
        "timezone",
        "transaction_id",
        "reference_no",
    ]
    numeric_fields = ["amount"]
    date_fields = ["date", "due_date"]
    duplicate_subset = ["date", "counterparty", "invoice_no", "amount", "transaction_direction"]

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
        working_df = normalize_text_columns(working_df, ["counterparty", "description", "invoice_no", "counterparty_type", "currency", "timezone"])
        working_df["transaction_direction"] = working_df["transaction_direction"].map(normalize_debt_receivable_direction)
        working_df["payment_status"] = working_df["payment_status"].map(normalize_payment_status)
        working_df["counterparty_type"] = working_df["counterparty_type"].map(
            lambda value: COUNTERPARTY_TYPE_ALIASES.get(str(value).lower(), str(value).lower()) if value else None
        )

        invalid_rows = []
        for _, row in working_df.iterrows():
            missing_fields = []
            if row.get("date") is pd.NaT or pd.isna(row.get("date")):
                missing_fields.append("date")
            if not row.get("counterparty"):
                missing_fields.append("counterparty")
            if (row.get("amount") or ZERO) <= ZERO:
                missing_fields.append("amount")
            if row.get("transaction_direction") not in {"debt", "receivable"}:
                missing_fields.append("transaction_direction")
            if missing_fields:
                invalid_rows.append(int(row[ROW_TRACKING_COLUMN]))
                append_dropped_row_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field=",".join(missing_fields),
                    message=f"Cari hareket kurallarina uymadigi icin satir atildi: {', '.join(missing_fields)}",
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

        if working_df.empty:
            return self.finalize_validation_result(
                dataframe=working_df,
                warnings=warnings,
                audit_context=context,
                missing_fields=["date", "counterparty", "amount", "transaction_direction"],
                message="Cari hesap takip raporu icin cari adi, tarih, yon ve tutar gereklidir.",
            )

        working_df = isoformat_dates(working_df, self.date_fields)
        return self.finalize_validation_result(dataframe=working_df, warnings=warnings, audit_context=context)

    def generate(self, df: pd.DataFrame, output_path: str | None = None, audit_context: dict | None = None) -> dict:
        working_df = df.copy()
        warnings = list(df.attrs.get("warnings", []))
        audit_context = ensure_audit_context(audit_context or df.attrs.get("audit_context"), self.report_definition)
        working_df["borc"] = working_df.apply(
            lambda row: to_decimal(row["amount"], default=ZERO) if row["transaction_direction"] == "debt" else ZERO,
            axis=1,
        )
        working_df["alacak"] = working_df.apply(
            lambda row: to_decimal(row["amount"], default=ZERO) if row["transaction_direction"] == "receivable" else ZERO,
            axis=1,
        )
        working_df["is_open"] = working_df["payment_status"] != "paid"
        reference_date = today_date()

        currency_summary = build_currency_summary(
            working_df,
            amount_fields=["amount"],
            warnings=warnings,
            audit_context=audit_context,
        )
        group_fields = ["counterparty", "counterparty_type"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])

        summary_rows = []
        for group_key, group in working_df.groupby(group_fields, dropna=False):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            counterparty = group_key[0]
            counterparty_type = group_key[1] if len(group_key) > 1 else None
            currency = group_key[2] if len(group_key) > 2 else currency_summary["reporting_currency"]
            open_group = group.loc[group["is_open"]]
            overdue_group = open_group.loc[
                open_group["due_date"].map(lambda value: bool(value) and (overdue_days(value, reference_date=reference_date) or 0) > 0)
            ]
            total_debt = decimal_series_sum(group["borc"])
            total_receivable = decimal_series_sum(group["alacak"])
            open_debt = decimal_series_sum(open_group["borc"])
            open_receivable = decimal_series_sum(open_group["alacak"])
            overdue_debt = decimal_series_sum(overdue_group["borc"])
            overdue_receivable = decimal_series_sum(overdue_group["alacak"])
            summary_rows.append(
                {
                    "Cari": counterparty,
                    "Cari Tipi": counterparty_type,
                    **({"Para Birimi": currency} if currency_summary["mixed_currency_detected"] else {}),
                    "Toplam Borc": round_money(total_debt),
                    "Toplam Alacak": round_money(total_receivable),
                    "Net Bakiye": round_money(total_receivable - total_debt),
                    "Acik Borc": round_money(open_debt),
                    "Acik Alacak": round_money(open_receivable),
                    "Net Acik Pozisyon": round_money(open_receivable - open_debt),
                    "Vadesi Gecmis Borc": round_money(overdue_debt),
                    "Vadesi Gecmis Alacak": round_money(overdue_receivable),
                }
            )
        summary_df = pd.DataFrame(summary_rows)

        movement_rows = working_df.rename(
            columns={
                "date": "Tarih",
                "counterparty": "Cari",
                "description": "Aciklama",
                "due_date": "Vade",
                "payment_status": "Odeme Durumu",
                "currency": "Para Birimi",
            }
        )
        movement_rows["Borc"] = working_df["borc"].map(round_money)
        movement_rows["Alacak"] = working_df["alacak"].map(round_money)
        movement_columns = ["Tarih", "Cari", "Aciklama", "Borc", "Alacak", "Vade", "Odeme Durumu"]
        if currency_summary["mixed_currency_detected"]:
            movement_columns.append("Para Birimi")
        movement_rows = movement_rows[movement_columns]

        aging_rows = build_aging_rows(working_df, currency_summary["mixed_currency_detected"])

        total_open_debt = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(summary_df["Acik Borc"]))
        total_open_receivable = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(summary_df["Acik Alacak"]))

        return self.build_result(
            df=df,
            warnings=warnings,
            summary={
                "open_debt": total_open_debt,
                "open_receivable": total_open_receivable,
                "net_open_position": None if currency_summary["mixed_currency_detected"] else round_money((to_decimal(total_open_receivable, default=ZERO) or ZERO) - (to_decimal(total_open_debt, default=ZERO) or ZERO)),
                **currency_summary,
            },
            tables={
                "summary": summary_df.to_dict(orient="records"),
                "movements": movement_rows.to_dict(orient="records"),
                "aging": aging_rows.to_dict(orient="records"),
            },
            sheets=[
                {
                    "name": "Cari Bakiye Ozeti",
                    "data": summary_df,
                    "currency_columns": [
                        "Toplam Borc",
                        "Toplam Alacak",
                        "Net Bakiye",
                        "Acik Borc",
                        "Acik Alacak",
                        "Net Acik Pozisyon",
                        "Vadesi Gecmis Borc",
                        "Vadesi Gecmis Alacak",
                    ],
                },
                {
                    "name": "Cari Hareketler",
                    "data": movement_rows,
                    "currency_columns": ["Borc", "Alacak"],
                    "date_columns": ["Tarih", "Vade"],
                },
                {
                    "name": "Yaslandirma Analizi",
                    "data": aging_rows,
                    "currency_columns": [
                        "Borc 0-30 Gun",
                        "Borc 31-60 Gun",
                        "Borc 61-90 Gun",
                        "Borc 90+ Gun",
                        "Alacak 0-30 Gun",
                        "Alacak 31-60 Gun",
                        "Alacak 61-90 Gun",
                        "Alacak 90+ Gun",
                    ],
                },
            ],
        )


def build_aging_rows(df: pd.DataFrame, include_currency: bool) -> pd.DataFrame:
    rows = []
    group_fields = ["counterparty"] + (["currency"] if include_currency else [])
    for group_key, group in df.groupby(group_fields, dropna=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        counterparty = group_key[0]
        currency = group_key[1] if len(group_key) > 1 else None
        buckets = {
            "Borc 0-30 Gun": 0.0,
            "Borc 31-60 Gun": 0.0,
            "Borc 61-90 Gun": 0.0,
            "Borc 90+ Gun": 0.0,
            "Alacak 0-30 Gun": 0.0,
            "Alacak 31-60 Gun": 0.0,
            "Alacak 61-90 Gun": 0.0,
            "Alacak 90+ Gun": 0.0,
        }
        for _, row in group.iterrows():
            if row.get("payment_status") == "paid" or not row.get("due_date"):
                continue
            days = overdue_days(row["due_date"], reference_date=today_date())
            if row["transaction_direction"] == "debt":
                bucket_prefix = "Borc"
            else:
                bucket_prefix = "Alacak"
            if days is None or days <= 30:
                buckets[f"{bucket_prefix} 0-30 Gun"] += round_money(row["amount"])
            elif days <= 60:
                buckets[f"{bucket_prefix} 31-60 Gun"] += round_money(row["amount"])
            elif days <= 90:
                buckets[f"{bucket_prefix} 61-90 Gun"] += round_money(row["amount"])
            else:
                buckets[f"{bucket_prefix} 90+ Gun"] += round_money(row["amount"])
        rows.append({"Cari": counterparty, **({"Para Birimi": currency} if include_currency else {}), **buckets})
    return pd.DataFrame(rows)
