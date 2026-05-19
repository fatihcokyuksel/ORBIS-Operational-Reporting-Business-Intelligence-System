from __future__ import annotations

import pandas as pd

from config import settings
from reports.base_agent import BaseReportAgent
from utils.audit_utils import ensure_audit_context
from utils.date_utils import to_period_string
from utils.money_utils import ZERO, compare_money_values, quantize_money, round_money, safe_divide, to_decimal
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
    normalize_transaction_type,
    resolve_duplicate_rows,
)
from utils.warning_utils import append_dropped_row_warning, append_invalid_value_warning


TRANSACTION_TYPE_ALIASES = {
    "sale": "sale",
    "sales": "sale",
    "satis": "sale",
    "refund": "refund",
    "return": "refund",
    "iade": "refund",
    "credit_note": "refund",
    "exchange": "exchange",
    "partial_refund": "partial_refund",
    "partial_return": "partial_refund",
    "correction": "correction",
}
SALE_TRANSACTION_TYPES = {"sale", "exchange", "correction"}
REFUND_TRANSACTION_TYPES = {"refund", "partial_refund"}
SUPPORTED_TRANSACTION_TYPES = SALE_TRANSACTION_TYPES | REFUND_TRANSACTION_TYPES


class ReportAgent(BaseReportAgent):
    required_fields = ["date", "product_name", "customer"]
    optional_fields = [
        "quantity",
        "unit_price",
        "discount",
        "salesperson",
        "region",
        "total_sales",
        "counterparty",
        "transaction_type",
        "return_status",
        "currency",
        "timezone",
        "transaction_id",
        "reference_no",
    ]
    numeric_fields = ["quantity", "unit_price", "discount", "total_sales"]
    date_fields = ["date"]
    duplicate_subset = ["date", "customer", "product_name", "quantity", "unit_price", "total_sales"]

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
        working_df = normalize_text_columns(working_df, ["product_name", "customer", "salesperson", "region", "counterparty", "currency", "timezone", "transaction_type", "return_status"])
        working_df["raw_transaction_type"] = working_df["transaction_type"]
        working_df["raw_return_status"] = working_df["return_status"]
        working_df["transaction_type"] = working_df["transaction_type"].map(normalize_sales_transaction_type)
        working_df["return_status"] = working_df["return_status"].map(normalize_sales_return_status).fillna("none")
        working_df["customer"] = working_df["customer"].fillna(working_df["counterparty"])
        working_df["discount"] = working_df["discount"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)
        working_df["quantity"] = working_df["quantity"].map(to_decimal)
        working_df["unit_price"] = working_df["unit_price"].map(to_decimal)
        working_df["total_sales"] = working_df["total_sales"].map(to_decimal)

        invalid_rows = set()
        for index, row in working_df.iterrows():
            row_number = int(row[ROW_TRACKING_COLUMN])
            transaction_type = row.get("transaction_type")
            raw_transaction_type = row.get("raw_transaction_type")
            return_status = row.get("return_status")
            quantity = to_decimal(row.get("quantity"))
            unit_price = to_decimal(row.get("unit_price"))
            total_sales = to_decimal(row.get("total_sales"))
            discount = to_decimal(row.get("discount"), default=ZERO) or ZERO

            if raw_transaction_type and (transaction_type is None or pd.isna(transaction_type)):
                invalid_rows.add(row_number)
                append_invalid_value_warning(
                    warnings,
                    warning_type="unknown_transaction_type",
                    severity="warning",
                    row=row_number,
                    field="transaction_type",
                    input_value=raw_transaction_type,
                    audit_context=context,
                    action="row_dropped",
                    value=raw_transaction_type,
                    message="Taninmayan transaction_type bulundu.",
                )
                continue

            if (raw_transaction_type is None or pd.isna(raw_transaction_type)) and return_status in {"partial_return", "return", "refund"}:
                append_invalid_value_warning(
                    warnings,
                    warning_type="return_status_detected",
                    severity="info",
                    row=row_number,
                    field="return_status",
                    input_value=return_status,
                    audit_context=context,
                    action="row_retained",
                    value=return_status,
                    message="Iade durumu bilgi olarak tutuldu. transaction_type sale kabul edildi.",
                )

            if transaction_type in REFUND_TRANSACTION_TYPES:
                append_invalid_value_warning(
                    warnings,
                    warning_type="refund_detected",
                    severity="info",
                    row=row_number,
                    field="transaction_type",
                    input_value=transaction_type,
                    audit_context=context,
                    action="row_retained",
                    value=transaction_type,
                    message="Refund/iade islemi net satis hesabina dahil edildi.",
                )

            if quantity is not None and quantity <= ZERO:
                invalid_rows.add(row_number)
                append_dropped_row_warning(
                    warnings,
                    row=row_number,
                    field="quantity",
                    input_value=round_money(quantity),
                    message="Miktar sifir veya negatif oldugu icin satir atildi.",
                    audit_context=context,
                    warning_type="invalid_row_causing_drop",
                    severity="blocking",
                )
                continue

            if transaction_type in REFUND_TRANSACTION_TYPES and quantity is None:
                invalid_rows.add(row_number)
                append_dropped_row_warning(
                    warnings,
                    row=row_number,
                    field="quantity",
                    message="Refund satirinda quantity > 0 olmalidir.",
                    audit_context=context,
                    warning_type="missing_required_field",
                    severity="blocking",
                )
                continue

            if unit_price is not None and unit_price < ZERO:
                invalid_rows.add(row_number)
                append_dropped_row_warning(
                    warnings,
                    row=row_number,
                    field="unit_price",
                    input_value=round_money(unit_price),
                    message="Negatif birim fiyatli satir atildi.",
                    audit_context=context,
                    warning_type="invalid_row_causing_drop",
                    severity="blocking",
                )
                continue

            if quantity is not None and unit_price is not None:
                base_total_sales = quantize_money(quantity * unit_price - discount)
                calculated_total_sales = apply_transaction_total_sign(base_total_sales, transaction_type)
                if total_sales is None:
                    append_invalid_value_warning(
                        warnings,
                        warning_type="recalculated_total_sales",
                        severity="info",
                        row=row_number,
                        field="total_sales",
                        input_value=None,
                        calculated_value=round_money(calculated_total_sales),
                        calculated_from=["quantity", "unit_price", "discount"],
                        audit_context=context,
                        action="derived_value",
                        message="Toplam satis miktar, birim fiyat ve indirim uzerinden yeniden hesaplandi.",
                        lineage={"rule": "signed(quantity * unit_price - discount)", "source_fields": ["quantity", "unit_price", "discount", "transaction_type"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                    )
                elif not compare_money_values(total_sales, calculated_total_sales):
                    append_invalid_value_warning(
                        warnings,
                        warning_type="recalculated_total_sales",
                        severity="info",
                        row=row_number,
                        field="total_sales",
                        input_value=round_money(total_sales),
                        calculated_value=round_money(calculated_total_sales),
                        calculated_from=["quantity", "unit_price", "discount"],
                        audit_context=context,
                        action="used_calculated_value",
                        message="total_sales ile deterministic hesaplanan satis tutari tutarsizdi. Hesaplanan deger kullanildi.",
                        lineage={"rule": "signed(quantity * unit_price - discount)", "source_fields": ["quantity", "unit_price", "discount", "transaction_type"], "config_snapshot": {"WARNING_MISMATCH_TOLERANCE": str(settings.WARNING_MISMATCH_TOLERANCE)}},
                    )
                final_total_sales = calculated_total_sales
            elif total_sales is not None:
                normalized_total_sales = apply_transaction_total_sign(total_sales, transaction_type)
                if not compare_money_values(total_sales, normalized_total_sales):
                    append_invalid_value_warning(
                        warnings,
                        warning_type="recalculated_total_sales",
                        severity="info",
                        row=row_number,
                        field="total_sales",
                        input_value=round_money(total_sales),
                        calculated_value=round_money(normalized_total_sales),
                        calculated_from=["transaction_type", "total_sales"],
                        audit_context=context,
                        action="used_calculated_value",
                        message="transaction_type nedeniyle total_sales isareti normalize edildi.",
                        lineage={"rule": "transaction_type_signed_total", "source_fields": ["transaction_type", "total_sales"], "config_snapshot": {}},
                    )
                final_total_sales = quantize_money(normalized_total_sales)
            else:
                invalid_rows.add(row_number)
                append_dropped_row_warning(
                    warnings,
                    row=row_number,
                    field="total_sales",
                    message="Toplam satis hesabi icin gerekli alanlar bulunamadigi icin satir atildi.",
                    audit_context=context,
                    warning_type="missing_required_field",
                )
                continue

            if final_total_sales == ZERO:
                invalid_rows.add(row_number)
                append_dropped_row_warning(
                    warnings,
                    row=row_number,
                    field="total_sales",
                    message="Sifir tutarli satis satiri atildi.",
                    audit_context=context,
                    warning_type="invalid_row_causing_drop",
                )
                continue

            if transaction_type == "sale" and final_total_sales < ZERO:
                append_invalid_value_warning(
                    warnings,
                    warning_type="negative_sale_total",
                    severity="warning",
                    row=row_number,
                    field="total_sales",
                    input_value=round_money(final_total_sales),
                    audit_context=context,
                    action="row_retained",
                    message="Normal satis transaction'inda negatif toplam bulundu.",
                    lineage={"rule": "negative_sale_total_check", "source_fields": ["transaction_type", "total_sales"], "config_snapshot": {}},
                )

            working_df.at[index, "total_sales"] = final_total_sales
            working_df.at[index, "signed_quantity"] = calculate_signed_quantity(quantity, transaction_type)

        for _, row in working_df.iterrows():
            row_number = int(row[ROW_TRACKING_COLUMN])
            if row_number in invalid_rows:
                continue
            missing_fields = []
            if row.get("date") is pd.NaT or pd.isna(row.get("date")):
                missing_fields.append("date")
            if not row.get("product_name"):
                missing_fields.append("product_name")
            if not row.get("customer"):
                missing_fields.append("customer")
            if row.get("transaction_type") not in SUPPORTED_TRANSACTION_TYPES:
                missing_fields.append("transaction_type")
            if missing_fields:
                invalid_rows.add(row_number)
                append_dropped_row_warning(
                    warnings,
                    row=row_number,
                    field=",".join(missing_fields),
                    message=f"Satis verisi eksik oldugu icin satir atildi: {', '.join(missing_fields)}",
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
                missing_fields=["date", "product_name", "customer"],
                message="Satis performans raporu icin tarih, urun ve musteri bilgisi gereklidir.",
            )

        working_df["quantity"] = working_df["quantity"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)
        working_df["signed_quantity"] = working_df["signed_quantity"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)
        working_df = isoformat_dates(working_df, self.date_fields)
        return self.finalize_validation_result(dataframe=working_df, warnings=warnings, audit_context=context)

    def generate(self, df: pd.DataFrame, output_path: str | None = None, audit_context: dict | None = None) -> dict:
        working_df = df.copy()
        warnings = list(df.attrs.get("warnings", []))
        audit_context = ensure_audit_context(audit_context or df.attrs.get("audit_context"), self.report_definition)
        working_df["month"] = working_df["date"].map(lambda value: to_period_string(value))
        working_df["quantity"] = working_df["quantity"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)
        working_df["signed_quantity"] = working_df["signed_quantity"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)
        working_df["total_sales"] = working_df["total_sales"].map(lambda value: to_decimal(value, default=ZERO) or ZERO)
        working_df["unit_price"] = working_df["unit_price"].map(to_decimal)

        currency_summary = build_currency_summary(
            working_df,
            amount_fields=["total_sales"],
            warnings=warnings,
            audit_context=audit_context,
        )
        include_currency = currency_summary["mixed_currency_detected"]

        working_df["is_sale"] = working_df["transaction_type"].isin(SALE_TRANSACTION_TYPES)
        working_df["is_refund"] = working_df["transaction_type"].isin(REFUND_TRANSACTION_TYPES)

        product_sales = build_dimension_table(working_df, ["product_name"], "Urun", include_currency=include_currency, currency_field="currency")
        customer_sales = build_dimension_table(working_df, ["customer"], "Musteri", include_currency=include_currency, currency_field="currency")
        monthly_trend = build_monthly_trend(working_df, include_currency=include_currency, currency_field="currency")

        gross_sales = decimal_series_sum(working_df.loc[working_df["is_sale"] & (working_df["total_sales"] > ZERO), "total_sales"])
        refund_total = abs(decimal_series_sum(working_df.loc[working_df["is_refund"], "total_sales"]))
        net_sales = decimal_series_sum(working_df["total_sales"])
        gross_quantity = decimal_series_sum(working_df.loc[working_df["is_sale"], "quantity"])
        refund_quantity = decimal_series_sum(working_df.loc[working_df["is_refund"], "quantity"])
        net_quantity = decimal_series_sum(working_df["signed_quantity"])
        gross_order_count = int(working_df["is_sale"].sum())
        refund_order_count = int(working_df["is_refund"].sum())
        net_order_count = gross_order_count - refund_order_count

        net_sales_value = None if include_currency else round_money(net_sales)
        gross_sales_value = None if include_currency else round_money(gross_sales)
        refund_total_value = None if include_currency else round_money(refund_total)
        net_average_order_value = None if include_currency else round_money(safe_divide(net_sales, gross_order_count) or ZERO) if gross_order_count > 0 else 0.0

        top_product_by_revenue = None if include_currency or product_sales.empty else product_sales.sort_values("Net Satis", ascending=False).iloc[0]["Urun"]
        top_customer = None if include_currency or customer_sales.empty else customer_sales.sort_values("Net Satis", ascending=False).iloc[0]["Musteri"]
        top_salesperson = top_entity_from_rows(build_salesperson_table(working_df, include_currency=include_currency), "Satis Temsilcisi", include_currency=include_currency)
        top_product_by_quantity = top_quantity_product(working_df)

        summary_row = {
            "Brut Satis": gross_sales_value,
            "Toplam Iade": refund_total_value,
            "Net Satis": net_sales_value,
            "Toplam Adet": round_money(gross_quantity),
            "Toplam Iade Adedi": round_money(refund_quantity),
            "Net Adet": round_money(net_quantity),
            "Toplam Siparis": gross_order_count,
            "Toplam Iade Islemi": refund_order_count,
            "Net Siparis Sayisi": net_order_count,
            "Net Ortalama Siparis Degeri": net_average_order_value,
            "En Cok Satan Urun (Ciro)": top_product_by_revenue,
            "En Cok Satan Urun (Adet)": top_product_by_quantity,
            "En Buyuk Musteri": top_customer,
            "En Basarili Satis Temsilcisi": top_salesperson,
        }
        summary_sheet = pd.DataFrame([summary_row])

        return self.build_result(
            df=df,
            warnings=warnings,
            summary={
                "gross_sales": gross_sales_value,
                "refund_total": refund_total_value,
                "net_sales": net_sales_value,
                "gross_quantity": round_money(gross_quantity),
                "refund_quantity": round_money(refund_quantity),
                "net_quantity": round_money(net_quantity),
                "gross_order_count": gross_order_count,
                "refund_order_count": refund_order_count,
                "net_order_count": net_order_count,
                "net_average_order_value": net_average_order_value,
                "top_product_by_revenue": top_product_by_revenue,
                "top_product_by_quantity": top_product_by_quantity,
                "top_customer": top_customer,
                "top_salesperson": top_salesperson,
                "total_sales": net_sales_value,
                "total_quantity": round_money(net_quantity),
                "total_refund": refund_total_value,
                **currency_summary,
            },
            tables={
                "summary": summary_sheet.to_dict(orient="records"),
                "product_sales": product_sales.to_dict(orient="records"),
                "customer_sales": customer_sales.to_dict(orient="records"),
                "monthly_trend": monthly_trend.to_dict(orient="records"),
            },
            sheets=[
                {
                    "name": "Satis Ozeti",
                    "data": summary_sheet,
                    "currency_columns": ["Brut Satis", "Toplam Iade", "Net Satis", "Net Ortalama Siparis Degeri"],
                    "number_columns": ["Toplam Adet", "Toplam Iade Adedi", "Net Adet", "Toplam Siparis", "Toplam Iade Islemi", "Net Siparis Sayisi"],
                },
                {
                    "name": "Urun Bazli Satis",
                    "data": product_sales,
                    "currency_columns": ["Brut Satis", "Toplam Iade", "Net Satis", "Ortalama Birim Fiyat"],
                    "number_columns": ["Toplam Adet", "Toplam Iade Adedi", "Net Adet", "Toplam Siparis", "Toplam Iade Islemi", "Net Siparis Sayisi"],
                },
                {
                    "name": "Musteri Bazli Satis",
                    "data": customer_sales,
                    "currency_columns": ["Brut Satis", "Toplam Iade", "Net Satis"],
                    "number_columns": ["Toplam Siparis", "Toplam Iade Islemi", "Net Siparis Sayisi"],
                },
                {
                    "name": "Aylik Satis Trend",
                    "data": monthly_trend,
                    "currency_columns": ["Brut Satis", "Toplam Iade", "Net Satis"],
                    "number_columns": ["Brut Siparis", "Iade Islemi", "Net Siparis", "Net Adet"],
                },
            ],
        )


def normalize_sales_transaction_type(value) -> str | None:
    normalized = normalize_transaction_type(value, TRANSACTION_TYPE_ALIASES)
    if normalized is None:
        return "sale"
    if normalized in SUPPORTED_TRANSACTION_TYPES:
        return normalized
    return None


def normalize_sales_return_status(value) -> str | None:
    normalized = normalize_transaction_type(
        value,
        {
            "none": "none",
            "partial_return": "partial_return",
            "partial_refund": "partial_return",
            "return": "return",
            "refund": "refund",
        },
    )
    if normalized is None:
        return None
    return normalized


def apply_transaction_total_sign(total_sales, transaction_type: str | None):
    total_value = quantize_money(total_sales)
    if transaction_type in REFUND_TRANSACTION_TYPES:
        return -abs(total_value)
    return total_value


def calculate_signed_quantity(quantity, transaction_type: str | None):
    quantity_value = to_decimal(quantity, default=ZERO) or ZERO
    if transaction_type in REFUND_TRANSACTION_TYPES:
        return -quantity_value
    return quantity_value


def build_dimension_table(
    df: pd.DataFrame,
    group_fields: list[str],
    display_label: str,
    *,
    include_currency: bool,
    currency_field: str,
) -> pd.DataFrame:
    dimension_group_fields = list(group_fields) + ([currency_field] if include_currency else [])
    rows = []
    for group_key, group in df.groupby(dimension_group_fields, dropna=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        label_value = group_key[0]
        currency = group_key[-1] if include_currency else None
        row = build_aggregate_row(group, display_label, label_value)
        if include_currency:
            row["Para Birimi"] = currency
        rows.append(row)
    result = pd.DataFrame(rows)
    if result.empty:
        return result
    sort_columns = ["Net Satis", "Net Adet"] if "Net Adet" in result.columns else ["Net Satis"]
    return result.sort_values(sort_columns, ascending=[False] * len(sort_columns))


def build_salesperson_table(df: pd.DataFrame, *, include_currency: bool) -> pd.DataFrame:
    filtered = df.dropna(subset=["salesperson"]).copy()
    if filtered.empty:
        return pd.DataFrame()
    return build_dimension_table(filtered, ["salesperson"], "Satis Temsilcisi", include_currency=include_currency, currency_field="currency")


def build_aggregate_row(group: pd.DataFrame, label_key: str, label_value) -> dict:
    sale_mask = group["is_sale"]
    refund_mask = group["is_refund"]
    gross_sales = decimal_series_sum(group.loc[sale_mask & (group["total_sales"] > ZERO), "total_sales"])
    refund_total = abs(decimal_series_sum(group.loc[refund_mask, "total_sales"]))
    net_sales = decimal_series_sum(group["total_sales"])
    gross_quantity = decimal_series_sum(group.loc[sale_mask, "quantity"])
    refund_quantity = decimal_series_sum(group.loc[refund_mask, "quantity"])
    net_quantity = decimal_series_sum(group["signed_quantity"])
    gross_order_count = int(sale_mask.sum())
    refund_order_count = int(refund_mask.sum())

    return {
        label_key: label_value,
        "Brut Satis": round_money(gross_sales),
        "Toplam Iade": round_money(refund_total),
        "Net Satis": round_money(net_sales),
        "Toplam Adet": round_money(gross_quantity),
        "Toplam Iade Adedi": round_money(refund_quantity),
        "Net Adet": round_money(net_quantity),
        "Toplam Siparis": gross_order_count,
        "Toplam Iade Islemi": refund_order_count,
        "Net Siparis Sayisi": gross_order_count - refund_order_count,
        "Ortalama Birim Fiyat": round_money(decimal_series_mean(group.loc[group["unit_price"].notna(), "unit_price"])) if group["unit_price"].notna().any() else None,
    }


def build_monthly_trend(df: pd.DataFrame, *, include_currency: bool, currency_field: str) -> pd.DataFrame:
    monthly_group_fields = ["month"] + ([currency_field] if include_currency else [])
    rows = []
    for group_key, group in df.groupby(monthly_group_fields, dropna=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        month = group_key[0]
        currency = group_key[-1] if include_currency else None
        sale_mask = group["is_sale"]
        refund_mask = group["is_refund"]
        row = {
            "Ay": month,
            "Brut Satis": round_money(decimal_series_sum(group.loc[sale_mask & (group["total_sales"] > ZERO), "total_sales"])),
            "Toplam Iade": round_money(abs(decimal_series_sum(group.loc[refund_mask, "total_sales"]))),
            "Net Satis": round_money(decimal_series_sum(group["total_sales"])),
            "Brut Siparis": int(sale_mask.sum()),
            "Iade Islemi": int(refund_mask.sum()),
            "Net Siparis": int(sale_mask.sum()) - int(refund_mask.sum()),
            "Net Adet": round_money(decimal_series_sum(group["signed_quantity"])),
        }
        if include_currency:
            row["Para Birimi"] = currency
        rows.append(row)
    monthly = pd.DataFrame(rows)
    if monthly.empty:
        return monthly
    sort_columns = ["Ay"] + (["Para Birimi"] if include_currency else [])
    return monthly.sort_values(sort_columns)


def top_entity_from_rows(df: pd.DataFrame, label_field: str, *, include_currency: bool):
    if include_currency or df.empty:
        return None
    return df.sort_values("Net Satis", ascending=False).iloc[0][label_field]


def top_quantity_product(df: pd.DataFrame):
    if df.empty:
        return None
    product_quantity = (
        df.groupby("product_name", dropna=False)["signed_quantity"]
        .apply(decimal_series_sum)
        .sort_values(ascending=False)
    )
    if product_quantity.empty:
        return None
    return product_quantity.index[0]
