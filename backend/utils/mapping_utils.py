from __future__ import annotations

import pandas as pd

from utils.date_utils import to_iso_date
from utils.money_utils import to_float
from utils.text_normalization import normalize_text_for_match


COMMON_STANDARD_FIELDS = [
    "date",
    "description",
    "amount",
    "direction",
    "timezone",
    "category",
    "counterparty",
    "invoice_no",
    "transaction_id",
    "reference_no",
    "tax_rate",
    "tax_amount",
    "quantity",
    "unit_price",
    "product_name",
    "employee_name",
    "department",
    "due_date",
    "payment_status",
    "currency",
    "account_code",
    "project_code",
    "branch",
    "document_type",
    "notes",
    "opening_balance",
    "closing_balance",
    "balance_after_transaction",
    "debt_amount",
    "receivable_amount",
    "transaction_type",
    "return_status",
    "base_amount",
    "total_amount",
    "gross_salary",
    "bonus",
    "benefits",
    "employer_cost",
    "employer_extra_cost",
    "customer",
    "salesperson",
    "region",
    "discount",
    "total_sales",
    "counterparty_type",
    "transaction_direction",
    "net_salary",
    "income_tax",
    "stamp_tax",
    "sgk_employee",
    "sgk_employer",
    "total_employer_cost",
    "product_code",
    "unit_cost",
    "warehouse",
    "supplier",
    "sales_price",
    "product_category",
    "tax_type",
    "period",
]


FIELD_OUTPUT_TYPES = {
    "date": "date",
    "due_date": "date",
    "amount": "number",
    "tax_rate": "number",
    "tax_amount": "number",
    "quantity": "number",
    "unit_price": "number",
    "opening_balance": "number",
    "closing_balance": "number",
    "balance_after_transaction": "number",
    "debt_amount": "number",
    "receivable_amount": "number",
    "base_amount": "number",
    "total_amount": "number",
    "gross_salary": "number",
    "bonus": "number",
    "benefits": "number",
    "employer_cost": "number",
    "employer_extra_cost": "number",
    "discount": "number",
    "total_sales": "number",
    "net_salary": "number",
    "income_tax": "number",
    "stamp_tax": "number",
    "sgk_employee": "number",
    "sgk_employer": "number",
    "total_employer_cost": "number",
    "unit_cost": "number",
    "sales_price": "number",
    "direction": "enum",
    "timezone": "string",
    "transaction_type": "enum",
    "return_status": "enum",
    "transaction_direction": "enum",
}


FIELD_ALIASES = {
    "date": ["tarih", "islem tarihi", "fatura tarihi", "odeme tarihi", "tarih/date", "date"],
    "description": ["aciklama", "islem aciklamasi", "not", "detay", "notes", "description"],
    "amount": ["tutar", "amount", "toplam", "islem tutari", "hareket tutari"],
    "direction": ["yon", "direction", "islem yonu", "gelir gider", "borc alacak", "hareket tipi"],
    "timezone": ["timezone", "saat dilimi", "time zone", "tz"],
    "category": ["kategori", "category", "grup", "gider kalemi"],
    "counterparty": ["cari/firma", "cari", "firma", "musteri", "tedarikci", "unvan", "counterparty", "cari hesap"],
    "customer": ["musteri", "customer", "cari", "firma"],
    "invoice_no": ["fatura no", "fatura numarasi", "invoice no", "invoice_no", "belge no"],
    "transaction_id": ["transaction id", "islem id", "hareket id", "kayit id"],
    "reference_no": ["reference no", "referans no", "ref no", "belge referansi"],
    "tax_rate": ["kdv orani", "vergi orani", "vat rate", "tax rate", "oran"],
    "tax_amount": ["kdv tutari", "vergi tutari", "vat amount", "tax amount"],
    "quantity": ["miktar", "adet", "quantity", "qty"],
    "unit_price": ["birim fiyat", "unit price", "fiyat", "birim tutar"],
    "product_name": ["urun", "urun adi", "hizmet", "product", "product name", "malzeme"],
    "employee_name": ["personel", "personel adi", "ad soyad", "employee", "employee name", "personel id"],
    "department": ["departman", "department", "birim"],
    "due_date": ["vade", "vade tarihi", "due date", "son odeme tarihi"],
    "payment_status": ["odeme durumu", "payment status", "tahsilat durumu", "durum"],
    "currency": ["para birimi", "currency", "doviz"],
    "account_code": ["hesap kodu", "account code", "muhasebe kodu"],
    "project_code": ["proje kodu", "project code"],
    "branch": ["sube", "branch"],
    "document_type": ["belge tipi", "document type", "evrak tipi"],
    "notes": ["not", "notes", "ek aciklama"],
    "opening_balance": ["acilis bakiyesi", "opening balance"],
    "closing_balance": ["kapanis bakiyesi", "closing balance"],
    "balance_after_transaction": ["islem sonrasi bakiye", "balance after transaction", "bakiye"],
    "debt_amount": ["borc tutari", "borc", "debt amount", "debt", "debit", "gider", "cikis"],
    "receivable_amount": ["alacak tutari", "alacak", "receivable amount", "receivable", "credit", "gelir", "giris"],
    "transaction_type": ["islem tipi", "transaction type", "alis satis", "satis tipi", "tip"],
    "return_status": ["iade durumu", "return status", "refund status", "kismi iade durumu", "return state"],
    "base_amount": ["matrah", "base amount", "kdv haric tutar", "vergi matrahi"],
    "total_amount": ["genel toplam", "toplam tutar", "total amount", "kdv dahil tutar"],
    "gross_salary": ["brut maas", "gross salary", "brut ucret"],
    "bonus": ["prim", "bonus", "ikramiye"],
    "benefits": ["yan hak", "yan haklar", "benefit", "yemek", "yol"],
    "employer_cost": [
        "sgk isveren payi",
        "isveren sgk",
        "isveren sgk yuku",
        "isveren yuk",
        "sgk employer cost",
        "employer sgk cost",
        "employer social security",
    ],
    "employer_extra_cost": ["ek isveren maliyeti", "employer extra cost", "ek sgk maliyeti"],
    "salesperson": ["satis temsilcisi", "salesperson", "temsilci", "satici"],
    "region": ["bolge", "region", "sehir"],
    "discount": ["indirim", "discount"],
    "total_sales": ["toplam satis", "net satis", "sales total", "total sales"],
    "counterparty_type": ["cari tipi", "counterparty type", "musteri tedarikci"],
    "transaction_direction": ["borc alacak yonu", "transaction direction", "islem yonu", "yon"],
    "net_salary": ["net maas", "net salary", "odeme tutari"],
    "income_tax": ["gelir vergisi", "income tax"],
    "stamp_tax": ["damga vergisi", "stamp tax"],
    "sgk_employee": ["sgk isci payi", "sgk employee", "isci sgk"],
    "sgk_employer": ["sgk isveren payi", "sgk employer", "isveren sgk"],
    "total_employer_cost": [
        "isveren toplam maliyeti",
        "toplam isveren maliyeti",
        "total employer cost",
        "isveren maliyeti",
        "personel toplam maliyeti",
    ],
    "product_code": ["stok kodu", "urun kodu", "product code", "stock code"],
    "unit_cost": ["birim maliyet", "unit cost", "alis maliyeti"],
    "warehouse": ["depo", "warehouse"],
    "supplier": ["tedarikci", "supplier", "firma"],
    "sales_price": ["satis fiyati", "sales price"],
    "product_category": ["urun kategorisi", "product category", "stok grubu"],
    "tax_type": ["vergi turu", "tax type", "vergi tipi"],
    "period": ["donem", "period", "beyanname donemi"],
}


BOOLEAN_TRUE_VALUES = {"1", "true", "evet", "yes", "x"}


def fields_for_report(report_definition: dict) -> list[str]:
    input_contract = report_definition.get("input_contract", {})
    return list(
        dict.fromkeys(
            input_contract.get("required_fields", [])
            + input_contract.get("optional_fields", [])
        )
    )


def output_type_for_field(field_name: str) -> str:
    return FIELD_OUTPUT_TYPES.get(field_name, "string")


def empty_mapping(field_name: str) -> dict:
    return {
        "mapping_type": "not_available",
        "source_column": None,
        "source_columns": [],
        "rule_type": "none",
        "output_type": output_type_for_field(field_name),
        "default_value": None,
    }


def column_mapping(field_name: str, source_column: str | None) -> dict:
    if not source_column:
        return empty_mapping(field_name)
    return {
        "mapping_type": "column",
        "source_column": source_column,
        "source_columns": [source_column],
        "rule_type": "none",
        "output_type": output_type_for_field(field_name),
        "default_value": None,
    }


def derived_mapping(field_name: str, source_columns: list[str], rule_type: str) -> dict:
    return {
        "mapping_type": "derived",
        "source_column": None,
        "source_columns": source_columns,
        "rule_type": rule_type,
        "output_type": output_type_for_field(field_name),
        "default_value": None,
    }


def constant_mapping(field_name: str, default_value) -> dict:
    return {
        "mapping_type": "constant",
        "source_column": None,
        "source_columns": [],
        "rule_type": "none",
        "output_type": output_type_for_field(field_name),
        "default_value": default_value,
    }


def sanitize_mapping_for_report(mapping_json: dict, report_definition: dict | None) -> dict:
    if not isinstance(mapping_json, dict) or not report_definition:
        return mapping_json

    if report_definition.get("report_id") != "sales_performance_report":
        return mapping_json

    field_mappings = mapping_json.get("field_mappings")
    if not isinstance(field_mappings, dict):
        return mapping_json

    transaction_mapping = field_mappings.get("transaction_type")
    if not isinstance(transaction_mapping, dict):
        return mapping_json

    transaction_source = transaction_mapping.get("source_column")
    if not transaction_source:
        return mapping_json

    if match_field_by_alias(transaction_source, ["return_status"]) != "return_status":
        return mapping_json

    return_status_mapping = field_mappings.get("return_status", empty_mapping("return_status"))
    if not isinstance(return_status_mapping, dict):
        return_status_mapping = empty_mapping("return_status")

    if return_status_mapping.get("mapping_type") in {None, "not_available"} or not return_status_mapping.get("source_column"):
        field_mappings["return_status"] = column_mapping("return_status", transaction_source)

    field_mappings["transaction_type"] = empty_mapping("transaction_type")

    warning_message = (
        "Sales mapping otomatik duzeltildi: Iade Durumu/Return Status/Refund Status kolonu "
        "transaction_type yerine return_status olarak kullanildi."
    )
    warnings = list(mapping_json.get("warnings") or [])
    if warning_message not in warnings:
        warnings.append(warning_message)
    mapping_json["warnings"] = warnings
    return mapping_json


def normalize_dataframe_for_report(
    df: pd.DataFrame,
    mapping_json: dict,
    report_definition: dict,
    numeric_fields: list[str],
    date_fields: list[str],
) -> pd.DataFrame:
    fields = fields_for_report(report_definition)
    field_mappings = mapping_json.get("field_mappings", {})

    records = []
    for _, row in df.iterrows():
        record = {}
        for field_name in fields:
            mapping = field_mappings.get(field_name, empty_mapping(field_name))
            record[field_name] = resolve_field_value(
                row=row,
                mapping=mapping,
                field_name=field_name,
                report_definition=report_definition,
            )

        if all(is_blank_value(value) for value in record.values()):
            continue

        record = post_process_record(record, numeric_fields=numeric_fields, date_fields=date_fields)
        records.append(record)

    normalized_df = pd.DataFrame(records)
    for field_name in fields:
        if field_name not in normalized_df.columns:
            normalized_df[field_name] = pd.NA
    return normalized_df


def resolve_field_value(row, mapping: dict, field_name: str, report_definition: dict):
    mapping_type = mapping.get("mapping_type")

    if mapping_type == "column":
        return row.get(mapping.get("source_column"))
    if mapping_type == "constant":
        return mapping.get("default_value")
    if mapping_type == "derived":
        return apply_derived_rule(
            row=row,
            source_columns=mapping.get("source_columns", []),
            rule_type=mapping.get("rule_type"),
            field_name=field_name,
            report_definition=report_definition,
        )
    if mapping_type == "llm_infer_later":
        return infer_field_value(row=row, field_name=field_name)
    return None


def apply_derived_rule(row, source_columns: list[str], rule_type: str, field_name: str, report_definition: dict):
    if rule_type == "debit_credit_amount":
        left_column, right_column = directional_columns(source_columns)
        right_value = to_float(row.get(right_column), default=0.0) or 0.0
        left_value = to_float(row.get(left_column), default=0.0) or 0.0
        return right_value if abs(right_value) > 0 else left_value

    if rule_type in {"debit_credit_direction", "boolean_columns"}:
        left_column, right_column = directional_columns(source_columns)
        right_value = row.get(right_column)
        left_value = row.get(left_column)
        if rule_type == "boolean_columns":
            if normalize_text_for_match(right_value) in BOOLEAN_TRUE_VALUES:
                return positive_direction_value(field_name, report_definition)
            if normalize_text_for_match(left_value) in BOOLEAN_TRUE_VALUES:
                return negative_direction_value(field_name, report_definition)
            return None

        right_amount = to_float(right_value, default=0.0) or 0.0
        left_amount = to_float(left_value, default=0.0) or 0.0
        if abs(right_amount) > 0:
            return positive_direction_value(field_name, report_definition)
        if abs(left_amount) > 0:
            return negative_direction_value(field_name, report_definition)
        return None

    if rule_type == "signed_amount_direction":
        source_column = source_columns[0] if source_columns else None
        amount_value = to_float(row.get(source_column))
        if amount_value is None:
            return None
        if amount_value >= 0:
            return positive_direction_value(field_name, report_definition)
        return negative_direction_value(field_name, report_definition)

    return None


def infer_field_value(row, field_name: str):
    if field_name != "category":
        return None
    for source_name in ["category", "description", "product_name", "department"]:
        value = row.get(source_name)
        if not is_blank_value(value):
            return value
    return None


def post_process_record(record: dict, numeric_fields: list[str], date_fields: list[str]) -> dict:
    cleaned = {}
    for field_name, value in record.items():
        if field_name in numeric_fields:
            cleaned[field_name] = to_float(value)
            continue
        if field_name in date_fields:
            cleaned[field_name] = to_iso_date(value)
            continue
        if field_name in {"direction", "transaction_direction", "transaction_type", "return_status", "payment_status", "tax_type"}:
            cleaned[field_name] = normalize_text_value(value)
            continue
        cleaned[field_name] = clean_text_value(value)
    return cleaned


def normalize_text_value(value) -> str | None:
    cleaned = clean_text_value(value)
    if not cleaned:
        return None
    return cleaned.lower()


def clean_text_value(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def is_blank_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return bool(pd.isna(value))


def positive_direction_value(field_name: str, report_definition: dict) -> str:
    accepted = set(report_definition.get("input_contract", {}).get("accepted_directions", []))
    if field_name == "transaction_direction":
        return "receivable"
    if {"debt", "receivable"} & accepted:
        return "receivable"
    return "income"


def negative_direction_value(field_name: str, report_definition: dict) -> str:
    accepted = set(report_definition.get("input_contract", {}).get("accepted_directions", []))
    if field_name == "transaction_direction":
        return "debt"
    if {"debt", "receivable"} & accepted:
        return "debt"
    return "expense"


def directional_columns(source_columns: list[str]) -> tuple[str | None, str | None]:
    normalized_columns = {column: normalize_text_for_match(column) for column in source_columns}
    left_column = None
    right_column = None
    for column, normalized in normalized_columns.items():
        if any(keyword in normalized for keyword in ["borc", "debt", "debit", "gider", "cikis", "expense"]):
            left_column = column
        elif any(keyword in normalized for keyword in ["alacak", "credit", "receivable", "gelir", "giris", "income"]):
            right_column = column

    if left_column is None and source_columns:
        left_column = source_columns[0]
    if right_column is None and len(source_columns) > 1:
        right_column = source_columns[1]
    return left_column, right_column


def match_field_by_alias(column_name: str, candidate_fields: list[str]) -> str | None:
    normalized_column = normalize_text_for_match(column_name)
    best_match = None
    best_score = 0
    for field_name in candidate_fields:
        aliases = FIELD_ALIASES.get(field_name, [])
        for alias in aliases:
            normalized_alias = normalize_text_for_match(alias)
            score = 0
            if normalized_column == normalized_alias:
                score = 10
            elif normalized_alias and normalized_alias in normalized_column:
                score = 5
            if score > best_score:
                best_score = score
                best_match = field_name
    return best_match
