from __future__ import annotations

import pandas as pd

from config import settings
from reports.base_agent import BaseReportAgent
from utils.audit_utils import ensure_audit_context
from utils.date_utils import to_period_string
from utils.money_utils import ZERO, calculate_total_employer_cost, compare_money_values, round_money, safe_divide, to_decimal
from utils.reporting_utils import build_currency_summary, decimal_series_mean, decimal_series_sum
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
    resolve_duplicate_rows,
)
from utils.warning_utils import append_derived_value_warning, append_dropped_row_warning, append_warning_if_mismatch


class ReportAgent(BaseReportAgent):
    required_fields = ["date", "employee_name", "department", "gross_salary"]
    optional_fields = [
        "bonus",
        "benefits",
        "employer_cost",
        "employer_extra_cost",
        "total_employer_cost",
        "currency",
        "timezone",
        "transaction_id",
        "reference_no",
    ]
    numeric_fields = ["gross_salary", "bonus", "benefits", "employer_cost", "employer_extra_cost", "total_employer_cost"]
    date_fields = ["date"]
    duplicate_subset = ["date", "employee_name", "department", "gross_salary"]

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
            )
        working_df = working_df.loc[~blank_mask].copy()

        working_df = normalize_currency_column(working_df)
        working_df = normalize_timezone_column(working_df)
        working_df = normalize_numeric_columns(working_df, self.numeric_fields)
        working_df = normalize_date_columns(working_df, self.date_fields, warnings=warnings, audit_context=context)
        working_df = normalize_text_columns(working_df, ["employee_name", "department", "currency", "timezone"])

        for field_name in ["bonus", "benefits", "employer_extra_cost"]:
            working_df[field_name] = working_df[field_name].map(lambda value: to_decimal(value, default=ZERO) or ZERO)

        working_df["employer_cost"] = working_df["employer_cost"].map(to_decimal)
        working_df["total_employer_cost"] = working_df["total_employer_cost"].map(to_decimal)
        for index, row in working_df.iterrows():
            employer_cost_value, total_employer_cost = calculate_total_employer_cost(
                row.get("gross_salary"),
                employer_cost=row.get("employer_cost"),
                bonus=row.get("bonus"),
                benefits=row.get("benefits"),
                employer_extra_cost=row.get("employer_extra_cost"),
            )
            if row.get("employer_cost") is None:
                append_derived_value_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field="employer_cost",
                    calculated_value=round_money(employer_cost_value),
                    calculated_from=["gross_salary"],
                    audit_context=context,
                    message="Isveren ek maliyeti SGK oranina gore hesaplandi.",
                    lineage={"rule": "gross_salary * employer_sgk_rate", "source_fields": ["gross_salary"], "config_snapshot": {"EMPLOYER_SGK_RATE": str(employer_cost_value / (row.get("gross_salary") or ZERO)) if row.get("gross_salary") else None}},
                )
            if row.get("total_employer_cost") is None:
                append_derived_value_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field="total_employer_cost",
                    calculated_value=round_money(total_employer_cost),
                    calculated_from=["gross_salary", "employer_cost", "bonus", "benefits", "employer_extra_cost"],
                    audit_context=context,
                    message="Isveren toplam maliyeti deterministik olarak hesaplandi.",
                    lineage={"rule": "gross_salary + employer_cost + bonus + benefits + employer_extra_cost", "source_fields": ["gross_salary", "employer_cost", "bonus", "benefits", "employer_extra_cost"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                )
            elif not compare_money_values(row.get("total_employer_cost"), total_employer_cost):
                append_warning_if_mismatch(
                    warnings,
                    field="total_employer_cost",
                    row=int(row[ROW_TRACKING_COLUMN]),
                    input_value=round_money(row.get("total_employer_cost")),
                    calculated_value=round_money(total_employer_cost),
                    calculated_from=["gross_salary", "employer_cost", "bonus", "benefits", "employer_extra_cost"],
                    audit_context=context,
                    message="Input total_employer_cost ile hesaplanan isveren toplam maliyeti tutarsizdi. Hesaplanan deger kullanildi.",
                    lineage={"rule": "gross_salary + employer_cost + bonus + benefits + employer_extra_cost", "source_fields": ["gross_salary", "employer_cost", "bonus", "benefits", "employer_extra_cost"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                )
            working_df.at[index, "employer_cost"] = employer_cost_value
            working_df.at[index, "total_employer_cost"] = total_employer_cost

        invalid_rows = []
        for _, row in working_df.iterrows():
            missing_fields = []
            if row.get("date") is pd.NaT or pd.isna(row.get("date")):
                missing_fields.append("date")
            if not row.get("employee_name"):
                missing_fields.append("employee_name")
            if not row.get("department"):
                missing_fields.append("department")
            if (row.get("gross_salary") or ZERO) <= ZERO:
                missing_fields.append("gross_salary")
            if missing_fields:
                invalid_rows.append(int(row[ROW_TRACKING_COLUMN]))
                append_dropped_row_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field=",".join(missing_fields),
                    message=f"Zorunlu alan eksigi veya gecersizligi nedeniyle satir atildi: {', '.join(missing_fields)}",
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
                missing_fields=["employee_name", "department", "gross_salary", "date"],
                message="Personel gider analiz raporu icin personel, departman ve brut maas bilgisi gereklidir.",
            )

        working_df = isoformat_dates(working_df, self.date_fields)
        return self.finalize_validation_result(
            dataframe=working_df,
            warnings=warnings,
            audit_context=context,
        )

    def generate(self, df: pd.DataFrame, output_path: str | None = None, audit_context: dict | None = None) -> dict:
        working_df = df.copy()
        warnings = list(df.attrs.get("warnings", []))
        audit_context = ensure_audit_context(audit_context or df.attrs.get("audit_context"), self.report_definition)
        working_df["month"] = working_df["date"].map(lambda value: to_period_string(value))

        currency_summary = build_currency_summary(
            working_df,
            amount_fields=["gross_salary", "total_employer_cost"],
            warnings=warnings,
            audit_context=audit_context,
        )
        group_fields = ["department"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])

        dept_rows = []
        for group_key, group in working_df.groupby(group_fields, dropna=False):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            department = group_key[0]
            currency = group_key[1] if len(group_key) > 1 else currency_summary["reporting_currency"]
            total_employer_cost = decimal_series_sum(group["total_employer_cost"])
            person_count = int(group["employee_name"].nunique())
            dept_rows.append(
                {
                    "Departman": department,
                    **({"Para Birimi": currency} if currency_summary["mixed_currency_detected"] else {}),
                    "Personel Sayisi": person_count,
                    "Toplam Brut Maas": round_money(decimal_series_sum(group["gross_salary"])),
                    "Toplam Prim": round_money(decimal_series_sum(group["bonus"])),
                    "Toplam Yan Hak": round_money(decimal_series_sum(group["benefits"])),
                    "Toplam Isveren Maliyeti": round_money(total_employer_cost),
                    "Kisi Basi Ortalama Maliyet": round_money(safe_divide(total_employer_cost, person_count) or ZERO),
                }
            )
        summary_sheet = pd.DataFrame(dept_rows)

        detail_rows = working_df.rename(
            columns={
                "date": "Tarih",
                "employee_name": "Personel",
                "department": "Departman",
                "gross_salary": "Brut Maas",
                "bonus": "Prim",
                "benefits": "Yan Haklar",
                "employer_cost": "Isveren SGK/Yuk",
                "total_employer_cost": "Isveren Toplam Maliyeti",
                "currency": "Para Birimi",
            }
        )
        detail_columns = [
            "Tarih",
            "Personel",
            "Departman",
            "Brut Maas",
            "Prim",
            "Yan Haklar",
            "Isveren SGK/Yuk",
            "Isveren Toplam Maliyeti",
        ]
        if currency_summary["mixed_currency_detected"]:
            detail_columns.append("Para Birimi")
        detail_rows = detail_rows[detail_columns]

        monthly_rows = []
        monthly_group_fields = ["month"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])
        for group_key, group in working_df.groupby(monthly_group_fields, dropna=False):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            month = group_key[0]
            currency = group_key[1] if len(group_key) > 1 else currency_summary["reporting_currency"]
            monthly_rows.append(
                {
                    "Ay": month,
                    **({"Para Birimi": currency} if currency_summary["mixed_currency_detected"] else {}),
                    "Toplam Personel Maliyeti": round_money(decimal_series_sum(group["total_employer_cost"])),
                    "Ortalama Personel Maliyeti": round_money(decimal_series_mean(group["total_employer_cost"])),
                }
            )
        monthly_trend = pd.DataFrame(monthly_rows)

        total_employer_cost = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df["total_employer_cost"]))

        return self.build_result(
            df=df,
            warnings=warnings,
            summary={
                "total_employer_cost": total_employer_cost,
                "employee_count": int(working_df["employee_name"].nunique()),
                **currency_summary,
            },
            tables={
                "summary": summary_sheet.to_dict(orient="records"),
                "details": detail_rows.to_dict(orient="records"),
                "monthly_trend": monthly_trend.to_dict(orient="records"),
            },
            sheets=[
                {
                    "name": "Personel Gider Ozeti",
                    "data": summary_sheet,
                    "currency_columns": [
                        "Toplam Brut Maas",
                        "Toplam Prim",
                        "Toplam Yan Hak",
                        "Toplam Isveren Maliyeti",
                        "Kisi Basi Ortalama Maliyet",
                    ],
                    "number_columns": ["Personel Sayisi"],
                },
                {
                    "name": "Personel Detaylari",
                    "data": detail_rows,
                    "currency_columns": ["Brut Maas", "Prim", "Yan Haklar", "Isveren SGK/Yuk", "Isveren Toplam Maliyeti"],
                    "date_columns": ["Tarih"],
                },
                {
                    "name": "Aylik Trend",
                    "data": monthly_trend,
                    "currency_columns": ["Toplam Personel Maliyeti", "Ortalama Personel Maliyeti"],
                },
            ],
        )
