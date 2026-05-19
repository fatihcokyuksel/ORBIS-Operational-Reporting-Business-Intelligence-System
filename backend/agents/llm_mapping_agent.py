from __future__ import annotations

import json

from agents.heuristic_mapping_agent import create_heuristic_mapping
from services.llm_service import LLMService
from services.report.report_registry_service import ReportRegistryService
from utils.mapping_utils import fields_for_report, output_type_for_field


FIELD_MAPPING_SCHEMA = {
    "type": "object",
    "properties": {
        "mapping_type": {
            "type": "string",
            "enum": ["column", "derived", "constant", "not_available", "llm_infer_later"],
        },
        "source_column": {"type": "string", "nullable": True},
        "source_columns": {"type": "array", "items": {"type": "string"}},
        "rule_type": {
            "type": "string",
            "enum": ["none", "boolean_columns", "debit_credit_amount", "debit_credit_direction", "signed_amount_direction"],
        },
        "output_type": {"type": "string", "enum": ["string", "number", "date", "enum"]},
        "default_value": {"type": "string", "nullable": True},
    },
    "required": ["mapping_type", "source_column", "source_columns", "rule_type", "output_type", "default_value"],
}


def build_mapping_prompt(report_definition: dict, preview_json: dict, user_request: str = "") -> str:
    fields = fields_for_report(report_definition)
    payload = {
        "task": "financial_excel_mapping_only",
        "report_type": report_definition["report_id"],
        "report_name": report_definition["display_name"],
        "user_request": user_request,
        "required_fields": report_definition.get("input_contract", {}).get("required_fields", []),
        "optional_fields": report_definition.get("input_contract", {}).get("optional_fields", []),
        "preview": preview_json,
    }

    return f"""
Sen yalnizca finansal Excel kolon mapping'i ureten bir agentsin.

Kurallar:
- Hesaplama yapma.
- Rapor, tablo veya narrative uretme.
- Yalnizca kolon esleme, kategori tahmini icin llm_infer_later ve eksik alan uyarisi uret.
- JSON disinda hicbir metin dondurme.
- Sadece su field'ler icin mapping uret: {fields}
- source_column ve source_columns her zaman Girdi içindeki preview kolonlarından seçilmeli.
- Zorunlu alanlar map edilemiyorsa status failed don.
- JSON çıktısındaki "report_type" alanı kesinlikle Girdi içindeki "report_type" değeriyle birebir aynı olmalıdır (örn: "{report_definition["report_id"]}").
- `field_mappings` içindeki her bir alanın (field) mapping_type değerine göre aşağıdaki kurallara %100 uyması ŞARTTIR. Aksi halde schema validation hatası alınır:
  1. Eğer mapping_type "column" ise:
     - `source_column` değeri eşleşen Excel kolon adı olmalıdır (örn: "İşlem Tarihi" veya "Tutar").
     - `source_columns` değeri bu kolon adını içeren tek elemanlı bir liste olmalıdır (örn: ["İşlem Tarihi"]).
     - `rule_type` değeri kesinlikle "none" olmalıdır.
  2. Eğer mapping_type "derived" ise:
     - `source_columns` değeri boş olamaz, eşleşen Excel kolon adlarının listesi olmalıdır.
     - `rule_type` kesinlikle "none" dışında bir değer almalıdır: "debit_credit_amount", "debit_credit_direction", "signed_amount_direction", veya "boolean_columns".
  3. Eğer mapping_type "not_available" ise:
     - `source_column` kesinlikle null olmalıdır.
     - `source_columns` kesinlikle boş liste [] olmalıdır.
     - `rule_type` kesinlikle "none" olmalıdır.
  4. Eğer mapping_type "constant" ise:
     - `default_value` kesinlikle dolu bir string olmalıdır (null olamaz).
     - `rule_type` kesinlikle "none" olmalıdır.
  5. Eğer mapping_type "llm_infer_later" ise:
     - `rule_type` kesinlikle "none" olmalıdır.

Girdi:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""


def build_mapping_schema(report_definition: dict) -> dict:
    field_properties = {
        field_name: {
            **FIELD_MAPPING_SCHEMA,
            "properties": {
                **FIELD_MAPPING_SCHEMA["properties"],
                "output_type": {"type": "string", "enum": [output_type_for_field(field_name)]},
            },
        }
        for field_name in fields_for_report(report_definition)
    }

    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["passed", "failed"]},
            "report_type": {"type": "string"},
            "selected_sheet": {"type": "string", "nullable": True},
            "confidence": {"type": "number"},
            "missing_fields": {"type": "array", "items": {"type": "string"}},
            "field_mappings": {
                "type": "object",
                "properties": field_properties,
                "required": list(field_properties.keys()),
            },
            "warnings": {"type": "array", "items": {"type": "string"}},
            "message": {"type": "string", "nullable": True},
        },
        "required": ["status", "report_type", "selected_sheet", "confidence", "missing_fields", "field_mappings", "warnings", "message"],
    }


def create_mapping_with_llm(report_type: str, preview_json: dict, user_request: str = "") -> dict:
    report_definition = ReportRegistryService().get_report_definition(report_type)
    llm = LLMService()
    return llm.generate_json(
        prompt=build_mapping_prompt(report_definition, preview_json, user_request=user_request),
        response_schema=build_mapping_schema(report_definition),
    )


def create_mapping(report_type: str, preview_json: dict, user_request: str = "") -> dict:
    try:
        return create_mapping_with_llm(
            report_type=report_type,
            preview_json=preview_json,
            user_request=user_request,
        )
    except Exception as exc:
        return create_heuristic_mapping(
            report_type=report_type,
            preview_json=preview_json,
            reason=str(exc),
        )
