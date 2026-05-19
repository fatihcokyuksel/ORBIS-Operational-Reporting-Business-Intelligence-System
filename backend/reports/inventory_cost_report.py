from __future__ import annotations

from collections import Counter

import pandas as pd

from config import settings
from reports.base_agent import BaseReportAgent
from utils.audit_utils import ensure_audit_context
from utils.money_utils import ZERO, quantize_money, round_money, to_decimal
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
from utils.warning_utils import append_dropped_row_warning, append_invalid_value_warning


DISPLAY_COST_METHOD = "Weighted Average"
INVENTORY_TYPE_ALIASES = {
    "stock_in": "stock_in",
    "giris": "stock_in",
    "stok giris": "stock_in",
    "in": "stock_in",
    "stock_out": "stock_out",
    "cikis": "stock_out",
    "stok cikis": "stock_out",
    "out": "stock_out",
}


class ReportAgent(BaseReportAgent):
    required_fields = ["date", "quantity", "transaction_type"]
    optional_fields = [
        "unit_cost",
        "product_code",
        "product_name",
        "warehouse",
        "supplier",
        "sales_price",
        "product_category",
        "currency",
        "timezone",
        "transaction_id",
        "reference_no",
    ]
    numeric_fields = ["quantity", "unit_cost", "sales_price"]
    date_fields = ["date"]
    duplicate_subset = ["date", "product_code", "product_name", "quantity", "transaction_type", "unit_cost"]

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
        working_df = normalize_text_columns(working_df, ["product_code", "product_name", "warehouse", "supplier", "product_category", "currency", "timezone"])
        working_df["transaction_type"] = working_df["transaction_type"].map(lambda value: normalize_transaction_type(value, INVENTORY_TYPE_ALIASES))
        working_df["unit_cost"] = working_df["unit_cost"].map(to_decimal)
        working_df["inventory_key"] = working_df.apply(build_inventory_key, axis=1)

        invalid_rows: list[int] = []
        for _, row in working_df.iterrows():
            missing_fields = []
            if row.get("date") is pd.NaT or pd.isna(row.get("date")):
                missing_fields.append("date")
            if not row.get("inventory_key"):
                missing_fields.append("product_code/product_name")
            if (row.get("quantity") or ZERO) <= ZERO:
                missing_fields.append("quantity")
            if row.get("transaction_type") not in {"stock_in", "stock_out"}:
                missing_fields.append("transaction_type")
            if row.get("transaction_type") == "stock_in" and (row.get("unit_cost") or ZERO) <= ZERO:
                missing_fields.append("unit_cost")
            if missing_fields:
                invalid_rows.append(int(row[ROW_TRACKING_COLUMN]))
                append_dropped_row_warning(
                    warnings,
                    row=int(row[ROW_TRACKING_COLUMN]),
                    field=",".join(missing_fields),
                    message=f"Stok maliyet kurallarina uymadigi icin satir atildi: {', '.join(missing_fields)}",
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

        emit_inconsistent_product_name_warnings(working_df, warnings=warnings, audit_context=context)

        if working_df.empty:
            return self.finalize_validation_result(
                dataframe=working_df,
                warnings=warnings,
                audit_context=context,
                missing_fields=["date", "quantity", "transaction_type"],
                message="Stok maliyet raporu icin urun, miktar, maliyet ve islem tipi gereklidir.",
            )

        working_df["input_total_cost"] = working_df.apply(
            lambda row: quantize_money((row.get("quantity") or ZERO) * ((row.get("unit_cost") or ZERO) if row.get("transaction_type") == "stock_in" else ZERO)),
            axis=1,
        )
        working_df = isoformat_dates(working_df, self.date_fields)
        return self.finalize_validation_result(dataframe=working_df, warnings=warnings, audit_context=context)

    def generate(self, df: pd.DataFrame, output_path: str | None = None, audit_context: dict | None = None) -> dict:
        working_df = df.copy()
        warnings = list(df.attrs.get("warnings", []))
        audit_context = ensure_audit_context(audit_context or df.attrs.get("audit_context"), self.report_definition)
        if "inventory_key" not in working_df.columns:
            working_df["inventory_key"] = working_df.apply(build_inventory_key, axis=1)
        if "input_total_cost" not in working_df.columns:
            working_df["input_total_cost"] = working_df.apply(
                lambda row: quantize_money((row.get("quantity") or ZERO) * ((row.get("unit_cost") or ZERO) if row.get("transaction_type") == "stock_in" else ZERO)),
                axis=1,
            )

        currency_summary = build_currency_summary(
            working_df,
            amount_fields=["input_total_cost"],
            warnings=warnings,
            audit_context=audit_context,
        )
        include_currency = currency_summary["mixed_currency_detected"]

        summary_rows_df, valuation_map = build_inventory_summary(
            working_df,
            include_currency=include_currency,
            warnings=warnings,
            audit_context=audit_context,
        )

        working_df["valuation_lookup_key"] = working_df.apply(
            lambda row: inventory_lookup_key(row.get("inventory_key"), row.get("currency"), include_currency),
            axis=1,
        )
        working_df["valuation_unit_cost"] = working_df.apply(
            lambda row: resolve_movement_valuation_unit_cost(row, valuation_map),
            axis=1,
        )
        working_df["valuation_total_cost"] = working_df.apply(
            lambda row: quantize_money((row.get("quantity") or ZERO) * (row.get("valuation_unit_cost") or ZERO)),
            axis=1,
        )
        working_df["Maliyet Yontemi"] = DISPLAY_COST_METHOD

        movement_rows = working_df.rename(
            columns={
                "date": "Tarih",
                "product_code": "Urun Kodu",
                "display_product_name": "Urun",
                "transaction_type": "Islem Tipi",
                "quantity": "Miktar",
                "unit_cost": "Input Birim Maliyet",
                "valuation_unit_cost": "Degerleme Birim Maliyeti",
                "valuation_total_cost": "Toplam Degerleme Maliyeti",
                "warehouse": "Depo",
                "currency": "Para Birimi",
            }
        )
        movement_rows["Urun Kodu"] = movement_rows["Urun Kodu"].fillna(working_df["inventory_key"])
        movement_rows["Urun"] = movement_rows["Urun"].fillna(working_df["inventory_key"])
        movement_columns = [
            "Tarih",
            "Urun Kodu",
            "Urun",
            "Islem Tipi",
            "Miktar",
            "Input Birim Maliyet",
            "Degerleme Birim Maliyeti",
            "Toplam Degerleme Maliyeti",
            "Depo",
            "Maliyet Yontemi",
        ]
        if include_currency:
            movement_columns.append("Para Birimi")
        movement_rows = movement_rows[movement_columns]

        critical_rows = summary_rows_df.loc[summary_rows_df["Kalan Stok"] <= 5].copy()
        critical_rows = critical_rows.rename(
            columns={
                "Urun Adi": "Urun",
                "Ortalama Birim Maliyet": "Ortalama Maliyet",
                "Toplam Stok Degeri": "Stok Degeri",
            }
        )
        critical_columns = ["Urun Kodu", "Urun", "Kalan Stok", "Ortalama Maliyet", "Stok Degeri", "Maliyet Yontemi"]
        if include_currency and "Para Birimi" in critical_rows.columns:
            critical_columns.insert(2, "Para Birimi")
        critical_rows = critical_rows[critical_columns]

        inventory_value = None if include_currency else round_money(decimal_series_sum(summary_rows_df["Toplam Stok Degeri"]))
        if include_currency and "Para Birimi" in summary_rows_df.columns:
            inventory_value_by_currency = {
                currency: {"inventory_value": round_money(decimal_series_sum(group["Toplam Stok Degeri"]))}
                for currency, group in summary_rows_df.groupby("Para Birimi", dropna=False)
            }
        else:
            inventory_value_by_currency = {
                currency_summary["reporting_currency"]: {"inventory_value": inventory_value or 0.0}
            }

        return self.build_result(
            df=df,
            warnings=warnings,
            summary={
                "inventory_value": inventory_value,
                "inventory_value_by_currency": inventory_value_by_currency,
                "cost_method": settings.DEFAULT_COST_METHOD,
                **currency_summary,
            },
            tables={
                "summary": summary_rows_df.to_dict(orient="records"),
                "movements": movement_rows.to_dict(orient="records"),
                "critical": critical_rows.to_dict(orient="records"),
            },
            sheets=[
                {
                    "name": "Stok Maliyet Ozeti",
                    "data": summary_rows_df,
                    "currency_columns": ["Ortalama Birim Maliyet", "Toplam Stok Degeri"],
                    "number_columns": ["Toplam Giris Miktari", "Toplam Cikis Miktari", "Kalan Stok"],
                },
                {
                    "name": "Stok Hareketleri",
                    "data": movement_rows,
                    "currency_columns": ["Input Birim Maliyet", "Degerleme Birim Maliyeti", "Toplam Degerleme Maliyeti"],
                    "number_columns": ["Miktar"],
                    "date_columns": ["Tarih"],
                },
                {
                    "name": "Kritik Stoklar",
                    "data": critical_rows,
                    "currency_columns": ["Ortalama Maliyet", "Stok Degeri"],
                    "number_columns": ["Kalan Stok"],
                },
            ],
        )


def build_inventory_key(row: pd.Series) -> str | None:
    product_code = row.get("product_code")
    if product_code:
        return product_code
    return row.get("product_name")


def inventory_lookup_key(inventory_key: str | None, currency: str | None, include_currency: bool):
    return (inventory_key, currency) if include_currency else inventory_key


def choose_display_name(group: pd.DataFrame, inventory_key: str | None) -> str | None:
    names = [name for name in group["product_name"].dropna().tolist() if str(name).strip()]
    if not names:
        return inventory_key
    counter = Counter(names)
    return counter.most_common(1)[0][0]


def choose_product_code(group: pd.DataFrame, inventory_key: str | None) -> str | None:
    codes = [code for code in group["product_code"].dropna().tolist() if str(code).strip()]
    if codes:
        return codes[0]
    return inventory_key


def emit_inconsistent_product_name_warnings(
    df: pd.DataFrame,
    *,
    warnings: list[dict],
    audit_context: dict | None = None,
):
    if df.empty or "inventory_key" not in df.columns:
        return

    for inventory_key, group in df.groupby("inventory_key", dropna=False, sort=False):
        if not group["product_code"].dropna().astype(str).str.strip().ne("").any():
            continue
        unique_names = []
        for name in group["product_name"].dropna().tolist():
            text = str(name).strip()
            if text and text not in unique_names:
                unique_names.append(text)
        if len(unique_names) <= 1:
            continue
        append_invalid_value_warning(
            warnings,
            warning_type="inconsistent_product_name",
            severity="warning",
            field="product_name",
            audit_context=audit_context,
            action="used_first_display_name",
            message="Ayni stok kodu icin birden fazla urun adi bulundu. Rapor product_code bazinda birlestirildi.",
            context={"product_code": inventory_key, "detected_names": unique_names},
        )


def build_inventory_summary(
    df: pd.DataFrame,
    *,
    include_currency: bool,
    warnings: list[dict],
    audit_context: dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    rows: list[dict] = []
    valuation_map: dict = {}
    group_fields = ["inventory_key"] + (["currency"] if include_currency else [])

    for group_key, group in df.groupby(group_fields, dropna=False, sort=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        inventory_key = group_key[0]
        currency = group_key[1] if len(group_key) > 1 else None
        lookup_key = inventory_lookup_key(inventory_key, currency, include_currency)
        in_rows = group.loc[group["transaction_type"] == "stock_in"].copy()
        out_rows = group.loc[group["transaction_type"] == "stock_out"].copy()

        total_in_qty = decimal_series_sum(in_rows["quantity"])
        total_out_qty = decimal_series_sum(out_rows["quantity"])
        total_in_cost = quantize_money(
            sum(
                (
                    (to_decimal(row.get("quantity"), default=ZERO) or ZERO)
                    * (to_decimal(row.get("unit_cost"), default=ZERO) or ZERO)
                )
                for _, row in in_rows.iterrows()
            )
        )
        average_cost = quantize_money(total_in_cost / total_in_qty) if total_in_qty > ZERO else ZERO
        remaining_stock = total_in_qty - total_out_qty
        effective_remaining_stock = remaining_stock if remaining_stock > ZERO else ZERO
        stock_value = quantize_money(effective_remaining_stock * average_cost)

        if remaining_stock < ZERO:
            append_invalid_value_warning(
                warnings,
                warning_type="negative_stock",
                severity="blocking" if settings.STRICT_INVENTORY_VALIDATION else "warning",
                field="inventory_key",
                audit_context=audit_context,
                action="stock_value_clamped_to_zero",
                input_value=inventory_key,
                calculated_value=round_money(remaining_stock),
                message="Stok cikisi stok girisinden fazla. Stok degeri negatif hesaplanmadi.",
                context={"inventory_key": inventory_key, "remaining_stock": round_money(remaining_stock)},
            )

        display_name = choose_display_name(group, inventory_key)
        product_code = choose_product_code(group, inventory_key)
        valuation_map[lookup_key] = average_cost
        for row_index in group.index:
            df.at[row_index, "display_product_name"] = display_name

        row = {
            "Urun Kodu": product_code,
            "Urun Adi": display_name,
            "Toplam Giris Miktari": round_money(total_in_qty),
            "Toplam Cikis Miktari": round_money(total_out_qty),
            "Kalan Stok": round_money(remaining_stock),
            "Ortalama Birim Maliyet": round_money(average_cost),
            "Toplam Stok Degeri": round_money(stock_value),
            "Maliyet Yontemi": DISPLAY_COST_METHOD,
        }
        if include_currency:
            row["Para Birimi"] = currency
        rows.append(row)

    summary_df = pd.DataFrame(rows)
    summary_columns = [
        "Urun Kodu",
        "Urun Adi",
        "Toplam Giris Miktari",
        "Toplam Cikis Miktari",
        "Kalan Stok",
        "Ortalama Birim Maliyet",
        "Toplam Stok Degeri",
        "Maliyet Yontemi",
    ]
    if include_currency:
        summary_columns.insert(2, "Para Birimi")
    if summary_df.empty:
        summary_df = pd.DataFrame(columns=summary_columns)
    else:
        summary_df = summary_df[summary_columns]
    return summary_df, valuation_map


def resolve_movement_valuation_unit_cost(row: pd.Series, valuation_map: dict):
    if row.get("transaction_type") == "stock_in":
        return to_decimal(row.get("unit_cost"), default=ZERO) or ZERO
    return valuation_map.get(row.get("valuation_lookup_key"), ZERO)
