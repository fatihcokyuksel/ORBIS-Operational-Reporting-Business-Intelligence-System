import pandas as pd

from config import settings
from normalizers.mapping_rule_builder import build_runtime_rules
from utils.date_utils import to_iso_date
from utils.money_utils import normalize_currency
from utils.text_normalization import normalize_text_for_match
from utils.text_numbers import parse_numeric_value


STANDARD_FIELDS = [
    "date",
    "description",
    "amount",
    "direction",
    "balance",
    "counterparty",
    "category",
    "currency",
    "timezone",
    "transaction_id",
    "invoice_no",
    "reference_no",
]


def normalize_excel_dataframe(
    df: pd.DataFrame,
    mapping_json: dict,
    report_type: str,
    intent: dict | None = None,
) -> list[dict]:
    field_mappings = mapping_json.get("field_mappings", {})
    runtime_rules = build_runtime_rules(mapping_json)
    transactions = []

    for _, row in df.iterrows():
        transaction = {}
        for field in STANDARD_FIELDS:
            mapping = field_mappings.get(field, {"mapping_type": "not_available"})
            transaction[field] = resolve_field_value(
                row=row,
                field_name=field,
                mapping=mapping,
                runtime_rule=runtime_rules.get(field),
                report_type=report_type,
            )

        amount = parse_numeric_value(transaction.get("amount"))
        if amount is None or amount == 0:
            continue

        transaction["amount"] = float(abs(amount))
        transaction["direction"] = normalize_direction(
            transaction.get("direction"),
            report_type=report_type,
        )
        transaction["date"] = normalize_date(transaction.get("date"), timezone_value=transaction.get("timezone"))
        transaction["description"] = normalize_text(transaction.get("description"))
        transaction["balance"] = normalize_optional_amount(transaction.get("balance"))
        transaction["counterparty"] = normalize_text(transaction.get("counterparty"))
        transaction["category"] = normalize_category(transaction)
        transaction["currency"] = normalize_currency(transaction.get("currency"), settings.DEFAULT_CURRENCY)
        transaction["timezone"] = normalize_text(transaction.get("timezone")) or settings.DEFAULT_TIMEZONE
        transaction["source"] = "excel"

        transactions.append(transaction)

    return transactions


def resolve_field_value(row, field_name: str, mapping: dict, runtime_rule: dict | None, report_type: str):
    mapping_type = mapping.get("mapping_type")

    if mapping_type == "column":
        return row.get(mapping.get("source_column"))

    if mapping_type == "constant":
        return mapping.get("default_value")

    if mapping_type in {"not_available", None}:
        return None

    if mapping_type == "llm_infer_later":
        if field_name == "category":
            return infer_category_from_description(row, mapping)
        return None

    if mapping_type == "derived" and runtime_rule:
        return apply_runtime_rule(row, field_name, runtime_rule, report_type)

    return None


def apply_runtime_rule(row, field_name: str, rule: dict, report_type: str):
    rule_type = rule.get("type")

    if rule_type == "debit_credit_amount":
        income_value = parse_numeric_value(row.get(rule["income_column"])) or 0
        expense_value = parse_numeric_value(row.get(rule["expense_column"])) or 0
        return income_value if abs(income_value) > 0 else expense_value

    if rule_type == "debit_credit_direction":
        income_value = parse_numeric_value(row.get(rule["income_column"])) or 0
        expense_value = parse_numeric_value(row.get(rule["expense_column"])) or 0
        income_raw = normalize_text_for_match(row.get(rule["income_column"], ""))
        expense_raw = normalize_text_for_match(row.get(rule["expense_column"], ""))
        yes_values = {"1", "true", "evet", "yes", "x"}
        if income_value == 0 and expense_value == 0:
            if income_raw in yes_values:
                return "receivable" if report_type == "debt_receivable_report" else "income"
            if expense_raw in yes_values:
                return "debt" if report_type == "debt_receivable_report" else "expense"
        if report_type == "debt_receivable_report":
            return "receivable" if abs(income_value) > 0 else "debt"
        return "income" if abs(income_value) > 0 else "expense"

    if rule_type == "boolean_columns" and field_name == "direction":
        income_raw = normalize_text_for_match(row.get(rule["income_column"], ""))
        expense_raw = normalize_text_for_match(row.get(rule["expense_column"], ""))
        yes_values = {"1", "true", "evet", "yes", "x"}
        if income_raw in yes_values:
            if report_type == "debt_receivable_report":
                return "receivable"
            return "income"
        if expense_raw in yes_values:
            if report_type == "debt_receivable_report":
                return "debt"
            return "expense"

    if rule_type == "signed_amount_direction" and field_name == "direction":
        amount_value = parse_numeric_value(row.get(rule["amount_column"])) or 0
        if report_type == "debt_receivable_report":
            return "receivable" if amount_value > 0 else "debt"
        return "income" if amount_value > 0 else "expense"

    return None


def normalize_direction(value, report_type: str) -> str | None:
    if value is None:
        return None

    text = normalize_text_for_match(value)
    if report_type == "debt_receivable_report":
        debt_aliases = {"expense", "gider", "cikis", "cikti", "odeme", "borc", "debit", "debt"}
        receivable_aliases = {"income", "gelir", "giris", "girdi", "tahsilat", "satis", "alacak", "credit", "receivable"}
        if text in debt_aliases:
            return "debt"
        if text in receivable_aliases:
            return "receivable"

    direction_aliases = {
        "income": "income",
        "inflow": "income",
        "gelir": "income",
        "giris": "income",
        "girdi": "income",
        "tahsilat": "income",
        "satis": "income",
        "alacak": "receivable" if report_type == "debt_receivable_report" else "income",
        "credit": "receivable" if report_type == "debt_receivable_report" else "income",
        "expense": "expense",
        "outflow": "expense",
        "gider": "expense",
        "cikis": "expense",
        "cikti": "expense",
        "odeme": "expense",
        "borc": "debt" if report_type == "debt_receivable_report" else "expense",
        "debit": "debt" if report_type == "debt_receivable_report" else "expense",
        "debt": "debt",
        "receivable": "receivable",
    }

    return direction_aliases.get(text, text)


def normalize_date(value, timezone_value: str | None = None) -> str | None:
    return to_iso_date(value, timezone_value=timezone_value)


def normalize_text(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_optional_amount(value) -> float | None:
    parsed = parse_numeric_value(value)
    return float(parsed) if parsed is not None else None


def normalize_category(transaction: dict) -> str:
    category = normalize_text(transaction.get("category"))
    if category:
        return category

    description = normalize_text_for_match(transaction.get("description") or "")
    keywords = {
        "kira": "Kira",
        "maas": "Personel",
        "personel": "Personel",
        "reklam": "Pazarlama",
        "pazarlama": "Pazarlama",
        "yazilim": "Yazilim",
        "satis": "Satis",
    }
    for keyword, label in keywords.items():
        if keyword in description:
            return label

    direction = transaction.get("direction")
    if direction == "income":
        return "Gelir"
    if direction == "expense":
        return "Gider"
    if direction == "debt":
        return "Borc"
    if direction == "receivable":
        return "Alacak"
    return "Diger"


def infer_category_from_description(row, mapping: dict) -> str | None:
    for column in mapping.get("source_columns", []):
        value = row.get(column)
        if value is not None:
            return normalize_text(value)
    return None
