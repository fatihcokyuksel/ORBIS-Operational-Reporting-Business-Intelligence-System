from __future__ import annotations

from decimal import Decimal

import pandas as pd

from config import settings
from reports.base_agent import BaseReportAgent
from utils.audit_utils import ensure_audit_context
from utils.money_utils import (
    ZERO,
    calculate_total_employer_cost,
    compare_money_values,
    round_money,
    safe_divide,
    to_decimal,
)
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
    resolve_duplicate_rows,
)
from utils.warning_utils import append_derived_value_warning, append_dropped_row_warning, append_warning_if_mismatch


class ReportAgent(BaseReportAgent):
    required_fields = ["date", "employee_name", "gross_salary", "net_salary"]
    optional_fields = [
        "department",
        "income_tax",
        "stamp_tax",
        "sgk_employee",
        "sgk_employer",
        "bonus",
        "benefits",
        "total_employer_cost",
        "currency",
        "timezone",
        "transaction_id",
        "reference_no",
    ]
    numeric_fields = [
        "gross_salary",
        "net_salary",
        "income_tax",
        "stamp_tax",
        "sgk_employee",
        "sgk_employer",
        "bonus",
        "benefits",
        "total_employer_cost",
    ]
    date_fields = ["date"]
    duplicate_subset = ["date", "employee_name", "gross_salary", "net_salary"]

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
        working_df = normalize_text_columns(working_df, ["employee_name", "department", "currency", "timezone"])

        for field_name in ["income_tax", "stamp_tax", "sgk_employee", "bonus", "benefits"]:
            working_df[field_name] = working_df[field_name].map(lambda value: to_decimal(value, default=ZERO) or ZERO)

        working_df["sgk_employer"] = working_df["sgk_employer"].map(to_decimal)
        working_df["total_employer_cost"] = working_df["total_employer_cost"].map(to_decimal)

        for index, row in working_df.iterrows():
            derived_sgk_employer = row.get("sgk_employer")
            if derived_sgk_employer is None:
                derived_sgk_employer = (to_decimal(row.get("gross_salary"), default=ZERO) or ZERO) * settings.EMPLOYER_SGK_RATE
                append_derived_value_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field="sgk_employer",
                    calculated_value=round_money(derived_sgk_employer),
                    calculated_from=["gross_salary"],
                    audit_context=context,
                    message="SGK isveren payi brut maas uzerinden hesaplandi.",
                    lineage={"rule": "gross_salary * employer_sgk_rate", "source_fields": ["gross_salary"], "config_snapshot": {"EMPLOYER_SGK_RATE": str(settings.EMPLOYER_SGK_RATE)}},
                )
            employer_cost_value, calculated_total = calculate_total_employer_cost(
                row.get("gross_salary"),
                employer_cost=derived_sgk_employer,
                bonus=row.get("bonus"),
                benefits=row.get("benefits"),
            )
            if row.get("total_employer_cost") is None:
                append_derived_value_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field="total_employer_cost",
                    calculated_value=round_money(calculated_total),
                    calculated_from=["gross_salary", "sgk_employer", "bonus", "benefits"],
                    audit_context=context,
                    message="Toplam isveren maliyeti deterministik olarak hesaplandi.",
                    lineage={"rule": "gross_salary + sgk_employer + bonus + benefits", "source_fields": ["gross_salary", "sgk_employer", "bonus", "benefits"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                )
            elif not compare_money_values(row.get("total_employer_cost"), calculated_total):
                append_warning_if_mismatch(
                    warnings,
                    field="total_employer_cost",
                    row=int(row[ROW_TRACKING_COLUMN]),
                    input_value=round_money(row.get("total_employer_cost")),
                    calculated_value=round_money(calculated_total),
                    calculated_from=["gross_salary", "sgk_employer", "bonus", "benefits"],
                    audit_context=context,
                    message="Input total_employer_cost ile hesaplanan toplam maliyet tutarsizdi. Hesaplanan deger kullanildi.",
                    lineage={"rule": "gross_salary + sgk_employer + bonus + benefits", "source_fields": ["gross_salary", "sgk_employer", "bonus", "benefits"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                )
            working_df.at[index, "sgk_employer"] = employer_cost_value
            working_df.at[index, "total_employer_cost"] = calculated_total

        invalid_rows = []
        for _, row in working_df.iterrows():
            missing_fields = []
            if row.get("date") is pd.NaT or pd.isna(row.get("date")):
                missing_fields.append("date")
            if not row.get("employee_name"):
                missing_fields.append("employee_name")
            if (row.get("gross_salary") or ZERO) <= ZERO:
                missing_fields.append("gross_salary")
            if (row.get("net_salary") or ZERO) <= ZERO:
                missing_fields.append("net_salary")
            if missing_fields:
                invalid_rows.append(int(row[ROW_TRACKING_COLUMN]))
                append_dropped_row_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field=",".join(missing_fields),
                    message=f"Maas verisi eksik veya gecersiz oldugu icin satir atildi: {', '.join(missing_fields)}",
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
                missing_fields=["date", "employee_name", "gross_salary", "net_salary"],
                message="Maas ve personel maliyet raporu icin personel, brut maas ve net maas alanlari gereklidir.",
            )

        working_df = isoformat_dates(working_df, self.date_fields)
        return self.finalize_validation_result(dataframe=working_df, warnings=warnings, audit_context=context)

    def generate(self, df: pd.DataFrame, output_path: str | None = None, audit_context: dict | None = None) -> dict:
        working_df = df.copy()
        warnings = list(df.attrs.get("warnings", []))
        audit_context = ensure_audit_context(audit_context or df.attrs.get("audit_context"), self.report_definition)
        working_df["toplam_vergi"] = working_df["income_tax"].map(lambda value: to_decimal(value, default=ZERO) or ZERO) + working_df["stamp_tax"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)
        working_df["toplam_sgk"] = working_df["sgk_employee"].map(lambda value: to_decimal(value, default=ZERO) or ZERO) + working_df["sgk_employer"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)

        currency_summary = build_currency_summary(
            working_df,
            amount_fields=["gross_salary", "net_salary", "total_employer_cost"],
            warnings=warnings,
            audit_context=audit_context,
        )
        dept_fields = ["department"] + (["currency"] if currency_summary["mixed_currency_detected"] else [])

        person_rows = working_df.rename(
            columns={
                "employee_name": "Personel",
                "department": "Departman",
                "gross_salary": "Brut Maas",
                "net_salary": "Net Maas",
                "toplam_vergi": "Vergiler",
                "toplam_sgk": "SGK",
                "bonus": "Prim",
                "total_employer_cost": "Isveren Maliyeti",
                "currency": "Para Birimi",
            }
        )
        person_columns = ["Personel", "Departman", "Brut Maas", "Net Maas", "Vergiler", "SGK", "Prim", "Isveren Maliyeti"]
        if currency_summary["mixed_currency_detected"]:
            person_columns.append("Para Birimi")
        person_rows = person_rows[person_columns]

        department_rows = []
        for group_key, group in working_df.groupby(dept_fields, dropna=False):
            if not isinstance(group_key, tuple):
                group_key = (group_key,)
            department = group_key[0]
            currency = group_key[1] if len(group_key) > 1 else currency_summary["reporting_currency"]
            total_employer_cost = decimal_series_sum(group["total_employer_cost"])
            employee_count = int(group["employee_name"].nunique())
            department_rows.append(
                {
                    "Departman": department,
                    **({"Para Birimi": currency} if currency_summary["mixed_currency_detected"] else {}),
                    "Personel Sayisi": employee_count,
                    "Toplam Isveren Maliyeti": round_money(total_employer_cost),
                    "Ortalama Maliyet": round_money(safe_divide(total_employer_cost, employee_count) or ZERO),
                }
            )
        dept_rows = pd.DataFrame(department_rows)

        total_gross_salary = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df["gross_salary"]))
        total_net_salary = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df["net_salary"]))
        total_tax = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df["toplam_vergi"]))
        total_sgk = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df["toplam_sgk"]))
        total_employer_cost = None if currency_summary["mixed_currency_detected"] else round_money(decimal_series_sum(working_df["total_employer_cost"]))

        summary_rows = [
            {"Metrik": "Toplam Brut Maas", "Deger": total_gross_salary},
            {"Metrik": "Toplam Net Maas", "Deger": total_net_salary},
            {"Metrik": "Toplam Vergi", "Deger": total_tax},
            {"Metrik": "Toplam SGK", "Deger": total_sgk},
            {"Metrik": "Toplam Isveren Maliyeti", "Deger": total_employer_cost},
        ]

        return self.build_result(
            df=df,
            warnings=warnings,
            summary={
                "total_employer_cost": total_employer_cost,
                "total_gross_salary": total_gross_salary,
                "total_net_salary": total_net_salary,
                "total_tax": total_tax,
                "total_sgk": total_sgk,
                **currency_summary,
            },
            tables={
                "summary": summary_rows,
                "person_rows": person_rows.to_dict(orient="records"),
                "department_rows": dept_rows.to_dict(orient="records"),
            },
            sheets=[
                {
                    "name": "Maas Ozeti",
                    "data": summary_rows,
                    "currency_columns": ["Deger"],
                },
                {
                    "name": "Personel Bazli Maliyet",
                    "data": person_rows,
                    "currency_columns": ["Brut Maas", "Net Maas", "Vergiler", "SGK", "Prim", "Isveren Maliyeti"],
                },
                {
                    "name": "Departman Bazli Maliyet",
                    "data": dept_rows,
                    "currency_columns": ["Toplam Isveren Maliyeti", "Ortalama Maliyet"],
                    "number_columns": ["Personel Sayisi"],
                },
            ],
        )
