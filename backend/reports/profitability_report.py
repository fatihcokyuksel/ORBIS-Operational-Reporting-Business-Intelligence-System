from __future__ import annotations

import pandas as pd

from reports.base_agent import BaseReportAgent
from utils.audit_utils import ensure_audit_context
from utils.date_utils import to_period_string
from utils.money_utils import ZERO, round_money, safe_divide, to_decimal
from utils.reporting_utils import build_currency_summary, decimal_series_sum
from utils.validation import (
    ROW_TRACKING_COLUMN,
    ensure_columns,
    ensure_row_tracking,
    is_blank_value,
    isoformat_dates,
    normalize_currency_column,
    normalize_date_columns,
    normalize_income_expense_direction,
    normalize_numeric_columns,
    normalize_text_columns,
    normalize_timezone_column,
    resolve_duplicate_rows,
)
from utils.warning_utils import append_dropped_row_warning


COGS_CATEGORIES = {"cogs", "smm", "satilan malin maliyeti", "cost of goods sold"}


class ReportAgent(BaseReportAgent):
    required_fields = ["date", "amount", "direction"]
    optional_fields = ["category", "description", "currency", "timezone", "transaction_id", "reference_no"]
    numeric_fields = ["amount"]
    date_fields = ["date"]
    duplicate_subset = ["date", "description", "amount", "direction"]

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
        working_df = normalize_text_columns(working_df, ["category", "description", "currency", "timezone"])
        working_df["direction"] = working_df["direction"].map(normalize_income_expense_direction)

        invalid_rows = []
        for _, row in working_df.iterrows():
            missing_fields = []
            if row.get("date") is pd.NaT or pd.isna(row.get("date")):
                missing_fields.append("date")
            if (row.get("amount") or ZERO) <= ZERO:
                missing_fields.append("amount")
            if row.get("direction") not in {"income", "expense"}:
                missing_fields.append("direction")
            if missing_fields:
                invalid_rows.append(int(row[ROW_TRACKING_COLUMN]))
                append_dropped_row_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field=",".join(missing_fields),
                    message=f"Gelir/gider kurallarina uymadigi icin satir atildi: {', '.join(missing_fields)}",
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
                missing_fields=["date", "amount", "direction"],
                message="Nakit bazli karlilik raporu icin gelir ve gider kayitlari gereklidir.",
            )

        working_df = isoformat_dates(working_df, self.date_fields)
        return self.finalize_validation_result(dataframe=working_df, warnings=warnings, audit_context=context)

    def generate(self, df: pd.DataFrame, output_path: str | None = None, audit_context: dict | None = None) -> dict:
        working_df = df.copy()
        warnings = list(df.attrs.get("warnings", []))
        audit_context = ensure_audit_context(audit_context or df.attrs.get("audit_context"), self.report_definition)
        working_df["month"] = working_df["date"].map(lambda value: to_period_string(value))

        currency_summary = build_currency_summary(
            working_df,
            amount_fields=["amount"],
            warnings=warnings,
            audit_context=audit_context,
        )

        income_df = working_df.loc[working_df["direction"] == "income"].copy()
        expense_df = working_df.loc[working_df["direction"] == "expense"].copy()
        cogs_df = expense_df.loc[expense_df["category"].fillna("").str.lower().isin(COGS_CATEGORIES)].copy()

        total_income = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(income_df["amount"]))
        total_expense = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(expense_df["amount"]))
        net_cash_profit_loss = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(income_df["amount"]) - decimal_series_sum(expense_df["amount"]))
        cash_profit_margin = None if currency_summary["mixed_currency_detected"] else round_money(safe_divide(net_cash_profit_loss, total_income) or ZERO) if total_income else None
        expense_income_ratio = None if currency_summary["mixed_currency_detected"] else round_money(safe_divide(total_expense, total_income) or ZERO) if total_income else None
        gross_profit = None
        if not currency_summary["mixed_currency_detected"] and not cogs_df.empty:
            gross_profit = round_money(decimal_series_sum(income_df["amount"]) - decimal_series_sum(cogs_df["amount"]))

        income_details = income_df.rename(
            columns={"date": "Tarih", "description": "Aciklama", "category": "Kategori", "amount": "Tutar", "currency": "Para Birimi"}
        )[["Tarih", "Aciklama", "Kategori", "Tutar"] + (["Para Birimi"] if currency_summary["mixed_currency_detected"] else [])]
        expense_details = expense_df.rename(
            columns={"date": "Tarih", "description": "Aciklama", "category": "Kategori", "amount": "Tutar", "currency": "Para Birimi"}
        )[["Tarih", "Aciklama", "Kategori", "Tutar"] + (["Para Birimi"] if currency_summary["mixed_currency_detected"] else [])]

        monthly_rows = []
        month_group_fields = ["month"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])
        for group_key, group in working_df.groupby(month_group_fields, dropna=False):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            month = group_key[0]
            currency = group_key[1] if len(group_key) > 1 else currency_summary["reporting_currency"]
            income_total = decimal_series_sum(group.loc[group["direction"] == "income", "amount"])
            expense_total = decimal_series_sum(group.loc[group["direction"] == "expense", "amount"])
            net_total = income_total - expense_total
            monthly_rows.append(
                {
                    "Ay": month,
                    **({"Para Birimi": currency} if currency_summary["mixed_currency_detected"] else {}),
                    "Gelir": round_money(income_total),
                    "Gider": round_money(expense_total),
                    "Net Nakit Bazli Kar/Zarar": round_money(net_total),
                    "Nakit Bazli Kar Marji": round_money(safe_divide(net_total, income_total) or ZERO) if income_total else None,
                }
            )
        monthly = pd.DataFrame(monthly_rows).sort_values("Ay") if monthly_rows else pd.DataFrame()

        summary_rows = [
            {"Metrik": "Toplam Gelir", "Tutar": total_income, "Oran": None},
            {"Metrik": "Toplam Gider", "Tutar": total_expense, "Oran": None},
            {"Metrik": "Net Nakit Bazli Kar/Zarar", "Tutar": net_cash_profit_loss, "Oran": None},
            {"Metrik": "Nakit Bazli Kar Marji", "Tutar": None, "Oran": cash_profit_margin},
            {"Metrik": "Gider/Gelir Orani", "Tutar": None, "Oran": expense_income_ratio},
        ]
        if gross_profit is not None:
            summary_rows.insert(2, {"Metrik": "Brut Kar", "Tutar": gross_profit, "Oran": None})

        return self.build_result(
            df=df,
            warnings=warnings,
            summary={
                "total_income": total_income,
                "total_expense": total_expense,
                "cash_profit": net_cash_profit_loss,
                "accounting_profit": None,
                "net_cash_profit_loss": net_cash_profit_loss,
                "net_profit": net_cash_profit_loss,
                **({"gross_profit": gross_profit} if gross_profit is not None else {}),
                **currency_summary,
            },
            tables={
                "summary": summary_rows,
                "income_details": income_details.to_dict(orient="records"),
                "expense_details": expense_details.to_dict(orient="records"),
                "monthly": monthly.to_dict(orient="records"),
            },
            sheets=[
                {"name": "Karlilik Ozeti", "data": summary_rows, "currency_columns": ["Tutar"], "percentage_columns": ["Oran"]},
                {"name": "Gelir Detaylari", "data": income_details, "currency_columns": ["Tutar"], "date_columns": ["Tarih"]},
                {"name": "Gider Detaylari", "data": expense_details, "currency_columns": ["Tutar"], "date_columns": ["Tarih"]},
                {
                    "name": "Aylik Karlilik",
                    "data": monthly,
                    "currency_columns": ["Gelir", "Gider", "Net Nakit Bazli Kar/Zarar"],
                    "percentage_columns": ["Nakit Bazli Kar Marji"],
                },
            ],
        )
