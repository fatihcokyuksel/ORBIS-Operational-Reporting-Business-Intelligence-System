from __future__ import annotations

import pandas as pd

from config import settings
from reports.base_agent import BaseReportAgent
from utils.audit_utils import ensure_audit_context
from utils.date_utils import to_period_string
from utils.money_utils import ZERO, calculate_tax_amount, compare_money_values, normalize_tax_rate, quantize_money, round_money, to_decimal
from utils.reporting_utils import build_currency_summary, decimal_series_sum
from utils.validation import (
    ROW_TRACKING_COLUMN,
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
    "sales": "sale",
    "satis": "sale",
    "output": "sale",
    "purchase": "purchase",
    "alis": "purchase",
    "buy": "purchase",
    "input": "purchase",
}


class ReportAgent(BaseReportAgent):
    required_fields = ["date", "base_amount", "tax_rate", "transaction_type"]
    optional_fields = [
        "tax_amount",
        "invoice_no",
        "counterparty",
        "product_name",
        "description",
        "currency",
        "total_amount",
        "timezone",
        "transaction_id",
        "reference_no",
    ]
    numeric_fields = ["base_amount", "tax_rate", "tax_amount", "total_amount"]
    date_fields = ["date"]
    duplicate_subset = ["date", "invoice_no", "counterparty", "base_amount", "tax_amount"]

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
        working_df = normalize_text_columns(working_df, ["invoice_no", "counterparty", "product_name", "description", "currency", "timezone"])
        working_df["transaction_type"] = working_df["transaction_type"].map(lambda value: normalize_transaction_type(value, TRANSACTION_TYPE_ALIASES))

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
                    message="KDV tutari matrah ve oran uzerinden hesaplandi.",
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
                    message="Input tax_amount ile hesaplanan KDV tutarsizdi. Hesaplanan deger kullanildi.",
                    lineage={"rule": "base_amount * tax_rate / 100", "source_fields": ["base_amount", "tax_rate"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                )
            total_amount = quantize_money((to_decimal(row.get("base_amount"), default=ZERO) or ZERO) + tax_amount)
            if row.get("total_amount") is None:
                append_derived_value_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field="total_amount",
                    calculated_value=round_money(total_amount),
                    calculated_from=["base_amount", "tax_amount"],
                    audit_context=context,
                    message="Toplam tutar matrah ve KDV uzerinden hesaplandi.",
                    lineage={"rule": "base_amount + tax_amount", "source_fields": ["base_amount", "tax_amount"], "config_snapshot": {}},
                )
            elif not compare_money_values(row.get("total_amount"), total_amount):
                append_warning_if_mismatch(
                    warnings,
                    field="total_amount",
                    row=int(row[ROW_TRACKING_COLUMN]),
                    input_value=round_money(row.get("total_amount")),
                    calculated_value=round_money(total_amount),
                    calculated_from=["base_amount", "tax_amount"],
                    audit_context=context,
                    message="Input total_amount ile hesaplanan toplam tutar tutarsizdi. Hesaplanan deger kullanildi.",
                    lineage={"rule": "base_amount + tax_amount", "source_fields": ["base_amount", "tax_amount"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                )
            working_df.at[index, "tax_rate"] = normalized_tax_rate
            working_df.at[index, "tax_amount"] = tax_amount
            working_df.at[index, "total_amount"] = total_amount

        for _, row in working_df.iterrows():
            missing_fields = []
            if row.get("date") is pd.NaT or pd.isna(row.get("date")):
                missing_fields.append("date")
            if (row.get("base_amount") or ZERO) <= ZERO:
                missing_fields.append("base_amount")
            if row.get("tax_rate") is None:
                missing_fields.append("tax_rate")
            if row.get("transaction_type") not in {"sale", "purchase"}:
                missing_fields.append("transaction_type")
            if missing_fields:
                invalid_rows.append(int(row[ROW_TRACKING_COLUMN]))
                append_dropped_row_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field=",".join(missing_fields),
                    message=f"Zorunlu alan eksigi nedeniyle satir atildi: {', '.join(missing_fields)}",
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
                missing_fields=["date", "base_amount", "tax_rate", "transaction_type"],
                message="KDV ozet raporu olusturmak icin matrah ve KDV orani gereklidir.",
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
            amount_fields=["tax_amount", "total_amount"],
            warnings=warnings,
            audit_context=audit_context,
        )
        vat_group_fields = ["tax_rate"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])

        vat_rows = []
        for group_key, group in working_df.groupby(vat_group_fields, dropna=False):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            tax_rate = group_key[0]
            currency = group_key[1] if len(group_key) > 1 else currency_summary["reporting_currency"]
            vat_rows.append(
                {
                    "KDV Orani": round_money(tax_rate),
                    **({"Para Birimi": currency} if currency_summary["mixed_currency_detected"] else {}),
                    "Satis Matrahi": round_money(decimal_series_sum(group.loc[group["transaction_type"] == "sale", "base_amount"])),
                    "Hesaplanan KDV": round_money(decimal_series_sum(group.loc[group["transaction_type"] == "sale", "tax_amount"])),
                    "Alis Matrahi": round_money(decimal_series_sum(group.loc[group["transaction_type"] == "purchase", "base_amount"])),
                    "Indirilecek KDV": round_money(decimal_series_sum(group.loc[group["transaction_type"] == "purchase", "tax_amount"])),
                }
            )
        vat_summary = pd.DataFrame(vat_rows)
        if not vat_summary.empty:
            vat_summary["Net KDV"] = vat_summary["Hesaplanan KDV"] - vat_summary["Indirilecek KDV"]

        details = working_df.rename(
            columns={
                "date": "Tarih",
                "invoice_no": "Fatura No",
                "counterparty": "Cari",
                "transaction_type": "Islem Tipi",
                "base_amount": "Matrah",
                "tax_rate": "KDV Orani",
                "tax_amount": "KDV Tutari",
                "total_amount": "Toplam",
                "currency": "Para Birimi",
            }
        )
        detail_columns = ["Tarih", "Fatura No", "Cari", "Islem Tipi", "Matrah", "KDV Orani", "KDV Tutari", "Toplam"]
        if currency_summary["mixed_currency_detected"]:
            detail_columns.append("Para Birimi")
        details = details[detail_columns]

        monthly_rows = []
        monthly_group_fields = ["month"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])
        for group_key, group in working_df.groupby(monthly_group_fields, dropna=False):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            month = group_key[0]
            currency = group_key[1] if len(group_key) > 1 else currency_summary["reporting_currency"]
            output_vat = decimal_series_sum(group.loc[group["transaction_type"] == "sale", "tax_amount"])
            input_vat = decimal_series_sum(group.loc[group["transaction_type"] == "purchase", "tax_amount"])
            monthly_rows.append(
                {
                    "Ay": month,
                    **({"Para Birimi": currency} if currency_summary["mixed_currency_detected"] else {}),
                    "Hesaplanan KDV": round_money(output_vat),
                    "Indirilecek KDV": round_money(input_vat),
                    "Net KDV": round_money(output_vat - input_vat),
                }
            )
        monthly = pd.DataFrame(monthly_rows).sort_values("Ay") if monthly_rows else pd.DataFrame()

        total_output_vat = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df.loc[working_df["transaction_type"] == "sale", "tax_amount"]))
        total_input_vat = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df.loc[working_df["transaction_type"] == "purchase", "tax_amount"]))

        return self.build_result(
            df=df,
            warnings=warnings,
            summary={
                "calculated_vat": total_output_vat,
                "deductible_vat": total_input_vat,
                "net_vat": None if currency_summary["mixed_currency_detected"] else round_money((to_decimal(total_output_vat, default=ZERO) or ZERO) - (to_decimal(total_input_vat, default=ZERO) or ZERO)),
                **currency_summary,
            },
            tables={
                "vat_summary": vat_summary.to_dict(orient="records"),
                "details": details.to_dict(orient="records"),
                "monthly": monthly.to_dict(orient="records"),
            },
            sheets=[
                {
                    "name": "KDV Ozeti",
                    "data": vat_summary,
                    "currency_columns": ["Satis Matrahi", "Hesaplanan KDV", "Alis Matrahi", "Indirilecek KDV", "Net KDV"],
                    "number_columns": ["KDV Orani"],
                },
                {
                    "name": "Fatura Detaylari",
                    "data": details,
                    "currency_columns": ["Matrah", "KDV Tutari", "Toplam"],
                    "number_columns": ["KDV Orani"],
                    "date_columns": ["Tarih"],
                },
                {
                    "name": "Aylik KDV Ozeti",
                    "data": monthly,
                    "currency_columns": ["Hesaplanan KDV", "Indirilecek KDV", "Net KDV"],
                },
            ],
        )
