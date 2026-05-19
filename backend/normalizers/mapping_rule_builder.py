from utils.text_normalization import normalize_text_for_match


def build_rule_for_field(field_name: str, mapping: dict) -> dict | None:
    rule_type = mapping.get("rule_type")
    source_columns = mapping.get("source_columns", [])

    if rule_type in [None, "none"]:
        return None

    if rule_type == "boolean_columns":
        income_column = find_column(source_columns, ["girdi", "giris", "gelir", "income", "in"])
        expense_column = find_column(source_columns, ["cikti", "cikis", "gider", "expense", "out"])

        if not income_column or not expense_column:
            raise ValueError(f"{field_name}: boolean_columns icin income/expense kolonlari bulunamadi.")

        return {
            "type": "boolean_columns",
            "income_column": income_column,
            "expense_column": expense_column,
        }

    if rule_type == "debit_credit_amount":
        income_column = find_column(source_columns, ["alacak", "credit", "income", "receivable"])
        expense_column = find_column(source_columns, ["borc", "debit", "expense", "debt"])

        if not income_column or not expense_column:
            raise ValueError(f"{field_name}: debit_credit_amount icin borc/alacak kolonlari bulunamadi.")

        return {
            "type": "debit_credit_amount",
            "income_column": income_column,
            "expense_column": expense_column,
        }

    if rule_type == "debit_credit_direction":
        income_column = find_column(source_columns, ["alacak", "credit", "income", "receivable"])
        expense_column = find_column(source_columns, ["borc", "debit", "expense", "debt"])

        if not income_column or not expense_column:
            raise ValueError(f"{field_name}: debit_credit_direction icin borc/alacak kolonlari bulunamadi.")

        return {
            "type": "debit_credit_direction",
            "income_column": income_column,
            "expense_column": expense_column,
        }

    if rule_type == "signed_amount_direction":
        amount_column = source_columns[0] if source_columns else None
        if not amount_column:
            raise ValueError(f"{field_name}: signed_amount_direction icin amount kolonu bulunamadi.")

        return {
            "type": "signed_amount_direction",
            "amount_column": amount_column,
        }

    raise ValueError(f"{field_name}: Desteklenmeyen rule_type: {rule_type}")


def build_runtime_rules(mapping_json: dict) -> dict:
    field_mappings = mapping_json.get("field_mappings", {})
    return {
        field_name: build_rule_for_field(field_name, mapping)
        for field_name, mapping in field_mappings.items()
    }


def find_column(columns: list[str], keywords: list[str]) -> str | None:
    for column in columns:
        normalized = normalize_text_for_match(column)
        for keyword in keywords:
            if keyword in normalized:
                return column
    return None


def enrich_mapping_with_rules(mapping_json: dict) -> dict:
    return mapping_json
