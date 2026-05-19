ALLOWED_MAPPING_TYPES = {
    "column",
    "derived",
    "constant",
    "not_available",
    "llm_infer_later",
}

ALLOWED_OUTPUT_TYPES = {
    "string",
    "number",
    "date",
    "enum",
}

ALLOWED_RULE_TYPES = {
    "none",
    "boolean_columns",
    "debit_credit_amount",
    "debit_credit_direction",
    "signed_amount_direction",
}

DEFAULT_ALLOWED_FIELDS = ["date", "description", "amount", "direction", "category"]
DEFAULT_REQUIRED_FIELDS_BY_REPORT = {
    "income_expense_report": ["date", "amount", "description", "direction"],
    "cash_flow_report": ["date", "amount", "description", "direction"],
    "debt_receivable_report": ["amount", "direction"],
}


def validate_mapping_format(report_type: str | None = None, mapping_json: dict | None = None, report_definition: dict | None = None) -> dict:
    errors = []
    warnings = []
    mapping_json = mapping_json or {}

    if not isinstance(mapping_json, dict):
        return {
            "valid": False,
            "errors": ["Mapping JSON dict formatinda degil."],
            "warnings": [],
        }

    expected_report_id = report_definition["report_id"] if report_definition else report_type
    if expected_report_id and mapping_json.get("report_type") != expected_report_id:
        errors.append(
            f"report_type uyumsuz. Beklenen: {expected_report_id}, Gelen: {mapping_json.get('report_type')}"
        )

    status = mapping_json.get("status")
    if status not in ["passed", "failed"]:
        errors.append("status sadece passed veya failed olabilir.")

    selected_sheet = mapping_json.get("selected_sheet")
    if status == "passed" and not selected_sheet:
        errors.append("status passed ise selected_sheet zorunludur.")

    field_mappings = mapping_json.get("field_mappings")
    if not isinstance(field_mappings, dict):
        errors.append("field_mappings object/dict olmali.")
        return {
            "valid": False,
            "errors": errors,
            "warnings": warnings,
        }

    required_fields = required_fields_for(report_type, report_definition)
    allowed_fields = allowed_fields_for(report_definition)

    for field in required_fields:
        if field not in field_mappings:
            errors.append(f"Zorunlu alan icin mapping yok: {field}")

    for field_name in field_mappings.keys():
        if field_name not in allowed_fields:
            warnings.append(f"Bu rapor icin beklenmeyen field mapping uretildi: {field_name}")

    for field_name, mapping in field_mappings.items():
        if not isinstance(mapping, dict):
            errors.append(f"{field_name}: mapping object/dict olmali.")
            continue

        mapping_type = mapping.get("mapping_type")
        source_column = mapping.get("source_column")
        source_columns = mapping.get("source_columns")
        rule_type = mapping.get("rule_type")
        output_type = mapping.get("output_type")

        if "rule" in mapping:
            errors.append(f"{field_name}: rule alani artik kullanilmiyor. Sadece rule_type kullanilmali.")

        if mapping_type not in ALLOWED_MAPPING_TYPES:
            errors.append(f"{field_name}: Gecersiz mapping_type: {mapping_type}")

        if output_type not in ALLOWED_OUTPUT_TYPES:
            errors.append(f"{field_name}: Gecersiz output_type: {output_type}")

        if rule_type not in ALLOWED_RULE_TYPES:
            errors.append(f"{field_name}: Gecersiz rule_type: {rule_type}")

        if not isinstance(source_columns, list):
            errors.append(f"{field_name}: source_columns liste olmali.")
            source_columns = []

        if mapping_type == "column":
            if not source_column:
                errors.append(f"{field_name}: column mapping icin source_column zorunlu.")
            if len(source_columns) != 1:
                errors.append(f"{field_name}: column mapping icin source_columns tek elemanli olmali.")
            if rule_type != "none":
                errors.append(f"{field_name}: column mapping icin rule_type none olmali.")

        elif mapping_type == "derived":
            if not source_columns:
                errors.append(f"{field_name}: derived mapping icin source_columns bos olamaz.")
            if rule_type == "none":
                errors.append(f"{field_name}: derived mapping icin rule_type none olamaz.")
            if field_name == "amount" and rule_type == "boolean_columns":
                errors.append("amount alani icin boolean_columns rule_type kullanilamaz.")
            if field_name == "direction" and rule_type == "debit_credit_amount":
                errors.append("direction alani icin debit_credit_amount rule_type kullanilamaz.")
            if field_name == "amount" and rule_type == "debit_credit_direction":
                errors.append("amount alani icin debit_credit_direction rule_type kullanilamaz.")
            if field_name == "amount" and rule_type == "signed_amount_direction":
                errors.append("amount alani icin signed_amount_direction rule_type kullanilamaz.")

        elif mapping_type == "not_available":
            if source_column is not None:
                errors.append(f"{field_name}: not_available icin source_column null olmali.")
            if source_columns:
                errors.append(f"{field_name}: not_available icin source_columns bos olmali.")
            if rule_type != "none":
                errors.append(f"{field_name}: not_available icin rule_type none olmali.")

        elif mapping_type == "constant":
            if mapping.get("default_value") is None:
                errors.append(f"{field_name}: constant mapping icin default_value zorunlu.")
            if rule_type != "none":
                errors.append(f"{field_name}: constant mapping icin rule_type none olmali.")

        elif mapping_type == "llm_infer_later":
            if rule_type != "none":
                errors.append(f"{field_name}: llm_infer_later icin rule_type none olmali.")

    for required_field in required_fields:
        field_mapping = field_mappings.get(required_field)
        if field_mapping and field_mapping.get("mapping_type") == "not_available":
            errors.append(f"Zorunlu alan not_available olamaz: {required_field}")

    if status == "passed" and errors:
        errors.append("LLM status passed verdi ama mapping validation hatali.")

    if status == "failed" and not mapping_json.get("missing_fields"):
        warnings.append("status failed ama missing_fields bos.")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


def required_fields_for(report_type: str | None, report_definition: dict | None) -> list[str]:
    if report_definition:
        return report_definition.get("input_contract", {}).get("required_fields", [])
    return DEFAULT_REQUIRED_FIELDS_BY_REPORT.get(report_type, [])


def allowed_fields_for(report_definition: dict | None) -> list[str]:
    if report_definition:
        required_fields = report_definition.get("input_contract", {}).get("required_fields", [])
        optional_fields = report_definition.get("input_contract", {}).get("optional_fields", [])
        return list(dict.fromkeys(DEFAULT_ALLOWED_FIELDS + required_fields + optional_fields))
    return DEFAULT_ALLOWED_FIELDS
