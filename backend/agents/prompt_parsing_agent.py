from __future__ import annotations

from datetime import date
import json
from io import StringIO

import pandas as pd

from services.report.report_registry_service import ReportRegistryService
from utils.mapping_utils import fields_for_report, match_field_by_alias


def create_intent(report_type: str, input_type: str, user_request: str) -> dict:
    return {
        "report_type": report_type,
        "input_type": input_type,
        "filters": {
            "date_range": infer_date_range(user_request),
            "categories": [],
        },
        "visual_preferences": {},
        "output_formats": ["json", "xlsx"],
    }


def infer_date_range(user_request: str) -> dict:
    text = user_request.lower()
    current_year = date.today().year
    months = {
        "ocak": 1,
        "subat": 2,
        "mart": 3,
        "nisan": 4,
        "mayis": 5,
        "haziran": 6,
        "temmuz": 7,
        "agustos": 8,
        "eylul": 9,
        "ekim": 10,
        "kasim": 11,
        "aralik": 12,
    }
    found = [number for name, number in months.items() if name in text]
    if not found:
        return {"start": None, "end": None}
    start_month = min(found)
    end_month = max(found)
    end_day = 31 if end_month in {1, 3, 5, 7, 8, 10, 12} else 30
    if end_month == 2:
        end_day = 29 if current_year % 4 == 0 else 28
    return {
        "start": f"{current_year}-{start_month:02d}-01",
        "end": f"{current_year}-{end_month:02d}-{end_day:02d}",
    }


def extract_prompt_transactions(prompt: str, report_type: str, intent: dict) -> dict:
    registry = ReportRegistryService()
    report_definition = registry.get_report_definition(report_type)
    expected_fields = fields_for_report(report_definition)

    records = parse_prompt_records(prompt)
    if not records:
        return {
            "status": "failed",
            "report_type": report_type,
            "transactions": [],
            "warnings": [],
            "message": "Prompt icinde parse edilebilir tablo veya JSON veri bulunamadi.",
        }

    standardized = [standardize_record(record, expected_fields) for record in records]
    standardized = [record for record in standardized if any(value not in [None, ""] for value in record.values())]

    if not standardized:
        return {
            "status": "failed",
            "report_type": report_type,
            "transactions": [],
            "warnings": [],
            "message": "Prompt verisi secilen raporun alanlarina donusturulemedi.",
        }

    return {
        "status": "passed",
        "report_type": report_type,
        "transactions": standardized,
        "warnings": [],
        "message": None,
    }


def parse_prompt_records(prompt: str) -> list[dict]:
    json_records = parse_json_records(prompt)
    if json_records is not None:
        return json_records

    table_records = parse_delimited_records(prompt)
    if table_records:
        return table_records

    return parse_key_value_blocks(prompt)


def parse_json_records(prompt: str) -> list[dict] | None:
    try:
        parsed = json.loads(prompt)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    if isinstance(parsed, dict):
        if isinstance(parsed.get("records"), list):
            return [item for item in parsed["records"] if isinstance(item, dict)]
        if isinstance(parsed.get("transactions"), list):
            return [item for item in parsed["transactions"] if isinstance(item, dict)]
        return [parsed]
    return None


def parse_delimited_records(prompt: str) -> list[dict]:
    text = prompt.strip()
    if not text:
        return []

    for separator in ["|", ";", ",", "\t"]:
        try:
            df = pd.read_csv(StringIO(text), sep=separator)
        except Exception:
            continue
        if len(df.columns) < 2 or df.empty:
            continue
        return df.to_dict(orient="records")
    return []


def parse_key_value_blocks(prompt: str) -> list[dict]:
    blocks = [block.strip() for block in prompt.split("\n\n") if block.strip()]
    records = []
    for block in blocks:
        record = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            record[key.strip()] = value.strip()
        if record:
            records.append(record)
    return records


def standardize_record(record: dict, expected_fields: list[str]) -> dict:
    standardized = {field_name: None for field_name in expected_fields}
    for key, value in record.items():
        if key in standardized:
            standardized[key] = value
            continue
        matched_field = match_field_by_alias(str(key), expected_fields)
        if matched_field:
            standardized[matched_field] = value
    return standardized
