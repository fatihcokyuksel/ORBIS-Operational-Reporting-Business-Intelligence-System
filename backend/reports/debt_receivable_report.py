from __future__ import annotations

import pandas as pd

from reports.base_agent import BaseReportAgent
from utils.audit_utils import ensure_audit_context
from utils.date_utils import is_overdue, today_date
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
from utils.warning_utils import append_dropped_row_warning, append_invalid_value_warning


COUNTERPARTY_TYPE_ALIASES = {
    "customer": "customer",
    "musteri": "customer",
    "müşteri": "customer",
    "supplier": "supplier",
    "vendor": "supplier",
    "tedarikci": "supplier",
    "tedarikçi": "supplier",
}


class ReportAgent(BaseReportAgent):
    required_fields = ["date", "counterparty", "amount", "direction"]
    optional_fields = [
        "counterparty_type",
        "description",
        "due_date",
        "invoice_no",
        "payment_status",
        "currency",
        "debt_amount",
        "receivable_amount",
        "timezone",
        "transaction_id",
        "reference_no",
    ]
    numeric_fields = ["amount", "debt_amount", "receivable_amount"]
    date_fields = ["date", "due_date"]
    duplicate_subset = ["date", "counterparty", "invoice_no", "amount", "direction"]

    def validate(self, df: pd.DataFrame, audit_context: dict | None = None) -> dict:
        context = ensure_audit_context(audit_context, self.report_definition)
        warnings: list[dict] = []
        working_df = ensure_row_tracking(ensure_columns(df, self.all_fields))

        blank_mask = working_df[self.all_fields].apply(lambda series: series.map(is_blank_value)).all(axis=1)
        for _, row in working_df.loc[blank_mask].iterrows():
            append_dropped_row_warning(
                warnings,
                row=int(row[ROW_TRACKING_COLUMN]),
                message="Bos satir temizlendi.",
                audit_context=context,
                severity="warning",
            )
        working_df = working_df.loc[~blank_mask].copy()

        working_df = normalize_currency_column(working_df)
        working_df = normalize_timezone_column(working_df)
        working_df = normalize_numeric_columns(working_df, self.numeric_fields)
        working_df = normalize_date_columns(working_df, self.date_fields, warnings=warnings, audit_context=context)
        working_df = normalize_text_columns(
            working_df,
            ["counterparty", "description", "invoice_no", "currency", "counterparty_type", "timezone"],
        )
        working_df["direction"] = working_df["direction"].map(normalize_debt_receivable_direction)
        working_df["payment_status"] = working_df["payment_status"].map(normalize_payment_status)
        working_df["counterparty_type"] = working_df["counterparty_type"].map(
            lambda value: COUNTERPARTY_TYPE_ALIASES.get(str(value).lower(), str(value).lower()) if value else None
        )
        working_df["debt_amount"] = working_df["debt_amount"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)
        working_df["receivable_amount"] = working_df["receivable_amount"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)
        working_df["amount"] = working_df["amount"].map(to_decimal)

        for index, row in working_df.iterrows():
            row_number = int(row[ROW_TRACKING_COLUMN])
            debt_amount = to_decimal(row.get("debt_amount"), default=ZERO) or ZERO
            receivable_amount = to_decimal(row.get("receivable_amount"), default=ZERO) or ZERO
            amount = to_decimal(row.get("amount"))
            direction = row.get("direction")

            if debt_amount > ZERO and receivable_amount <= ZERO:
                amount = debt_amount
                direction = "debt"
            elif receivable_amount > ZERO and debt_amount <= ZERO:
                amount = receivable_amount
                direction = "receivable"
            elif debt_amount > ZERO and receivable_amount > ZERO:
                append_invalid_value_warning(
                    warnings,
                    warning_type="invalid_value",
                    severity="warning",
                    row=row_number,
                    field="debt_amount,receivable_amount",
                    input_value={"debt_amount": round_money(debt_amount), "receivable_amount": round_money(receivable_amount)},
                    audit_context=context,
                    action="row_retained",
                    context={"debt_amount": round_money(debt_amount), "receivable_amount": round_money(receivable_amount)},
                    message="Borc ve alacak ayni satirda dolu. Satir inceleme gerektiriyor.",
                )
                if debt_amount >= receivable_amount:
                    amount = debt_amount
                    direction = "debt"
                else:
                    amount = receivable_amount
                    direction = "receivable"

            working_df.at[index, "direction"] = direction
            if direction == "debt" and debt_amount == ZERO:
                working_df.at[index, "debt_amount"] = amount or ZERO
            if direction == "receivable" and receivable_amount == ZERO:
                working_df.at[index, "receivable_amount"] = amount or ZERO
            working_df.at[index, "amount"] = amount or ZERO

        invalid_rows = []
        for _, row in working_df.iterrows():
            missing_fields = []
            if row.get("date") is pd.NaT or pd.isna(row.get("date")):
                missing_fields.append("date")
            if not row.get("counterparty"):
                missing_fields.append("counterparty")
            if row.get("direction") not in {"debt", "receivable"}:
                missing_fields.append("direction")
            if (row.get("amount") or ZERO) <= ZERO:
                missing_fields.append("amount")
            if missing_fields:
                invalid_rows.append(int(row[ROW_TRACKING_COLUMN]))
                append_dropped_row_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field=",".join(missing_fields),
                    message=f"Zorunlu alan veya tutar eksigi nedeniyle satir atildi: {', '.join(missing_fields)}",
                    audit_context=context,
                    warning_type="missing_required_field",
                    severity="warning",
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
                missing_fields=["date", "counterparty", "amount", "direction"],
                message="Borc-alacak raporu icin yeterli veri bulunamadi.",
            )

        working_df = isoformat_dates(working_df, self.date_fields)
        return self.finalize_validation_result(dataframe=working_df, warnings=warnings, audit_context=context)

    def generate(self, df: pd.DataFrame, output_path: str | None = None, audit_context: dict | None = None) -> dict:
        working_df = df.copy()
        warnings = list(df.attrs.get("warnings", []))
        audit_context = ensure_audit_context(audit_context or df.attrs.get("audit_context"), self.report_definition)
        reference_date = today_date()

        working_df["is_overdue"] = working_df.apply(
            lambda row: bool(row.get("due_date")) and is_overdue(row["due_date"], reference_date=reference_date) and row.get("payment_status") != "paid",
            axis=1,
        )

        currency_summary = build_currency_summary(
            working_df,
            amount_fields=["amount"],
            warnings=warnings,
            audit_context=audit_context,
        )
        group_fields = ["counterparty", "counterparty_type"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])

        main_rows = []
        top_risk_rows = []
        for group_key, group in working_df.groupby(group_fields, dropna=False):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            counterparty = group_key[0]
            counterparty_type = group_key[1] if len(group_key) > 1 else None
            currency = group_key[2] if len(group_key) > 2 else currency_summary["reporting_currency"]
            total_debt = decimal_series_sum(group["debt_amount"])
            total_receivable = decimal_series_sum(group["receivable_amount"])
            overdue_debt = decimal_series_sum(group.loc[group["is_overdue"], "debt_amount"])
            overdue_receivable = decimal_series_sum(group.loc[group["is_overdue"], "receivable_amount"])
            if counterparty_type == "customer":
                risk_score = overdue_receivable
            elif counterparty_type == "supplier":
                risk_score = overdue_debt
            else:
                risk_score = overdue_debt + overdue_receivable
            main_rows.append(
                {
                    "Cari/Firma": counterparty,
                    "Cari Tipi": counterparty_type,
                    **({"Para Birimi": currency} if currency_summary["mixed_currency_detected"] else {}),
                    "Toplam Borc": round_money(total_debt),
                    "Toplam Alacak": round_money(total_receivable),
                    "Net Durum": round_money(total_receivable - total_debt),
                    "Vadesi Gecmis Borc": round_money(overdue_debt),
                    "Vadesi Gecmis Alacak": round_money(overdue_receivable),
                    "Risk Skoru": round_money(risk_score),
                    "Risk Durumu": classify_risk(risk_score),
                }
            )
            top_risk_rows.append((counterparty, round_money(risk_score)))
        main_df = pd.DataFrame(main_rows).sort_values(["Risk Skoru", "Toplam Borc"], ascending=[False, False]) if main_rows else pd.DataFrame()

        detail_rows = working_df.assign(Borc=working_df["debt_amount"].map(round_money), Alacak=working_df["receivable_amount"].map(round_money))[
            ["date", "counterparty", "counterparty_type", "description", "Borc", "Alacak", "due_date", "payment_status", "currency"]
        ].rename(
            columns={
                "date": "Tarih",
                "counterparty": "Cari/Firma",
                "counterparty_type": "Cari Tipi",
                "description": "Aciklama",
                "due_date": "Vade Tarihi",
                "payment_status": "Odeme Durumu",
                "currency": "Para Birimi",
            }
        )
        if not currency_summary["mixed_currency_detected"]:
            detail_rows = detail_rows.drop(columns=["Para Birimi"])

        total_debt = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df["debt_amount"]))
        total_receivable = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df["receivable_amount"]))
        summary_rows = [
            {"Metrik": "Toplam Borc", "Deger": total_debt},
            {"Metrik": "Toplam Alacak", "Deger": total_receivable},
            {
                "Metrik": "Net Borc/Alacak",
                "Deger": None if currency_summary["mixed_currency_detected"] else round_money((to_decimal(total_receivable, default=ZERO) or ZERO) - (to_decimal(total_debt, default=ZERO) or ZERO)),
            },
        ]
        for counterparty, risk_score in sorted(top_risk_rows, key=lambda item: item[1], reverse=True)[:10]:
            summary_rows.append({"Metrik": f"Riskli Cari: {counterparty}", "Deger": risk_score})

        return self.build_result(
            df=df,
            warnings=warnings,
            summary={
                "total_debt": total_debt,
                "total_receivable": total_receivable,
                "net_position": None if currency_summary["mixed_currency_detected"] else round_money((to_decimal(total_receivable, default=ZERO) or ZERO) - (to_decimal(total_debt, default=ZERO) or ZERO)),
                **currency_summary,
            },
            tables={
                "main": main_df.to_dict(orient="records"),
                "details": detail_rows.to_dict(orient="records"),
                "summary": summary_rows,
            },
            sheets=[
                {
                    "name": "Ana Rapor",
                    "data": main_df,
                    "currency_columns": ["Toplam Borc", "Toplam Alacak", "Net Durum", "Vadesi Gecmis Borc", "Vadesi Gecmis Alacak", "Risk Skoru"],
                },
                {
                    "name": "Detayli Hareketler",
                    "data": detail_rows,
                    "currency_columns": ["Borc", "Alacak"],
                    "date_columns": ["Tarih", "Vade Tarihi"],
                },
                {"name": "Ozet", "data": summary_rows, "currency_columns": ["Deger"]},
            ],
        )


def classify_risk(risk_score) -> str:
    score = to_decimal(risk_score, default=ZERO) or ZERO
    if score <= ZERO:
        return "Dusuk"
    if score < to_decimal(50000, default=ZERO):
        return "Orta"
    return "Yuksek"
