import logging
import pandas as pd
import shutil
from pathlib import Path
from typing import Any

from agents.excel_parsing_agent import parse_excel_full
from agents.excel_preview_agent import create_excel_preview_json, save_preview_json
from agents.heuristic_mapping_agent import create_heuristic_mapping
from agents.llm_mapping_agent import create_mapping
from agents.prompt_parsing_agent import create_intent
from agents.report_generator_agent import generate_report
from outputs.output_generator import generate_outputs
from schemas.api_models import ReportGenerationResult, WarningItem
from schemas.report_filters import FilterApplicationSummary, ReportFilterSpec
from services.report.report_execution_service import ReportExecutionService
from services.analysis.ai_analysis_service import AIAnalysisService
from services.report.report_filter_defaults import get_report_filter_defaults
from services.report.report_filter_engine import apply_report_filters
from services.report.report_prompt_filter_service import extract_report_filters
from services.report.report_registry_service import ReportRegistryService
from services.report.report_suitability_service import (
    assess_excel_suitability,
    mapping_references_existing_columns,
    normalized_payload_is_usable,
)
from services.storage_service import StorageService
from utils.audit_utils import create_audit_context
from utils.date_utils import parse_date_value
from utils.mapping_utils import sanitize_mapping_for_report
from utils.warning_utils import append_invalid_value_warning
from validators.mapping_validator import validate_mapping_format
from validators.transaction_validator import validate_transactions

logger = logging.getLogger(__name__)

REGISTRY = ReportRegistryService()
EXECUTION = ReportExecutionService(REGISTRY)

def generate_report_from_excel(
    report_type: str,
    file_path: str,
    audit_run_id: str,
    output_format: str = "xlsx",
    user_prompt: str | None = None,
) -> ReportGenerationResult:
    try:
        report_definition = REGISTRY.get_report_definition(report_type)
    except KeyError:
        return ReportGenerationResult(
            status="failed",
            report_type=report_type,
            audit_run_id=audit_run_id,
            message="Desteklenmeyen rapor tipi."
        )

    intent = create_intent(
        report_type=report_type,
        input_type="excel",
        user_request=user_prompt or "",
    )
    
    # Audit context
    audit_context = create_audit_context(report_definition)
    audit_context["audit_run_id"] = audit_run_id

    try:
        preview_json = create_excel_preview_json(file_path)
        
        mapping_json = create_mapping(
            report_type=report_type,
            preview_json=preview_json,
            user_request=user_prompt or "",
        )
        mapping_json = sanitize_mapping_for_report(mapping_json, report_definition)

        validation_result = validate_mapping_format(
            report_type=report_type,
            mapping_json=mapping_json,
            report_definition=report_definition,
        )

        if not validation_result["valid"]:
            logger.warning(f"LLM Mapping Validation failed: {validation_result['errors']}. Mapping JSON was: {mapping_json}")
            fallback_mapping = create_heuristic_mapping(
                report_type=report_type,
                preview_json=preview_json,
                reason="LLM mapping schema validation basarisiz oldu.",
            )
            fallback_mapping = sanitize_mapping_for_report(fallback_mapping, report_definition)
            fallback_validation = validate_mapping_format(
                report_type=report_type,
                mapping_json=fallback_mapping,
                report_definition=report_definition,
            )
            if fallback_validation["valid"]:
                mapping_json = fallback_mapping
                validation_result = fallback_validation

        if not validation_result["valid"]:
            return ReportGenerationResult(
                status="failed",
                report_type=report_type,
                audit_run_id=audit_run_id,
                message="Mapping validation basarisiz.",
                errors=coerce_error_items(validation_result["errors"]),
                warnings=[WarningItem(**w) for w in validation_result["warnings"]]
            )

        column_reference_check = mapping_references_existing_columns(mapping_json, preview_json)
        if not column_reference_check["valid"]:
            fallback_mapping = create_heuristic_mapping(
                report_type=report_type,
                preview_json=preview_json,
                reason="LLM mapping preview kolonlariyla uyusmadi.",
            )
            fallback_mapping = sanitize_mapping_for_report(fallback_mapping, report_definition)
            fallback_validation = validate_mapping_format(
                report_type=report_type,
                mapping_json=fallback_mapping,
                report_definition=report_definition,
            )
            if fallback_validation["valid"]:
                mapping_json = fallback_mapping
                validation_result = fallback_validation

        suitability = assess_excel_suitability(
            report_definition=report_definition,
            mapping_json=mapping_json,
            preview_json=preview_json,
            registry_service=REGISTRY,
        )
        if suitability["status"] != "passed":
            return ReportGenerationResult(
                status="failed",
                report_type=report_type,
                audit_run_id=audit_run_id,
                message="Secilen rapor bu veri girisi ile uretilemiyor.",
                errors=[{"message": suitability.get("message")}]
            )

        warnings_list = validation_result["warnings"] + mapping_json.get("warnings", [])

        raw_df = parse_excel_full(
            file_path=file_path,
            sheet_name=mapping_json["selected_sheet"],
        )

        normalized_payload = EXECUTION.normalize_for_report(
            report_definition=report_definition,
            raw_data=raw_df,
            mapping_json=mapping_json,
            intent=intent,
        )

        if not normalized_payload_is_usable(
            normalized_payload["items"],
            report_definition,
            preview_json=preview_json,
            mapping_json=mapping_json,
        ):
            fallback_mapping = create_heuristic_mapping(
                report_type=report_type,
                preview_json=preview_json,
                reason="Ilk mapping normalize asamasinda kullanilabilir veri uretemedi.",
            )
            fallback_mapping = sanitize_mapping_for_report(fallback_mapping, report_definition)
            fallback_validation = validate_mapping_format(
                report_type=report_type,
                mapping_json=fallback_mapping,
                report_definition=report_definition,
            )
            if fallback_validation["valid"]:
                mapping_json = fallback_mapping
                normalized_payload = EXECUTION.normalize_for_report(
                    report_definition=report_definition,
                    raw_data=raw_df,
                    mapping_json=mapping_json,
                    intent=intent,
                )

        if not normalized_payload_is_usable(
            normalized_payload["items"],
            report_definition,
            preview_json=preview_json,
            mapping_json=mapping_json,
        ):
            return ReportGenerationResult(
                status="failed",
                report_type=report_type,
                audit_run_id=audit_run_id,
                message="Normalize edilen veri secilen rapor icin anlamli bir direction yapisi uretemedi."
            )

        normalized_df = pd.DataFrame(normalized_payload["items"])
        filter_spec = ReportFilterSpec()
        filter_summary = build_default_filter_summary(user_prompt, len(normalized_df))
        filter_warnings: list[dict] = []
        filtered_df = normalized_df.copy()

        if user_prompt and user_prompt.strip():
            defaults = get_report_filter_defaults(report_type)
            min_date, max_date = resolve_date_bounds(normalized_df, defaults.get("primary_date_field"))
            filter_spec = extract_report_filters(
                user_prompt=user_prompt,
                report_type=report_type,
                available_columns=list(normalized_df.columns),
                normalized_schema=list(normalized_df.columns),
                min_date=min_date,
                max_date=max_date,
            )
            filtered_df, filter_warnings, filter_summary = apply_report_filters(
                normalized_df,
                filter_spec=filter_spec,
                report_type=report_type,
                user_prompt=user_prompt.strip(),
            )
            if not filter_spec.has_actionable_filters():
                append_invalid_value_warning(
                    filter_warnings,
                    warning_type="filter_low_confidence",
                    severity="warning",
                    action="filter_not_applied",
                    message="Kullanici isteginden uygulanabilir filtre cikarilamadi. Rapor tum veriyle hazirlandi.",
                    context={"confidence": filter_spec.confidence, "notes": filter_spec.notes},
                )
            if filter_summary.filtered_row_count == 0:
                return ReportGenerationResult(
                    status="failed",
                    report_type=report_type,
                    audit_run_id=audit_run_id,
                    message="Uygulanan filtrelerden sonra rapor uretecek veri kalmadi.",
                    warnings=[coerce_warning_item(w) for w in filter_warnings],
                    filter=filter_summary.model_dump(),
                )

        warnings_list = validation_result["warnings"] + mapping_json.get("warnings", []) + filter_warnings
        validation_filters: dict[str, Any] = {}

        validation = validate_transactions(
            transactions=filtered_df.to_dict(orient="records"),
            report_definition=report_definition,
            filters=validation_filters,
            audit_context=audit_context,
        )

        if not validation["valid"]:
            error_items = coerce_error_items(validation["errors"])
            error_message = "Veri validation basarisiz."
            if any("rapor uretecek veri kalmadi" in str(item.get("message", "")).lower() for item in error_items):
                error_message = "Filtre ve validation sonrasi rapor uretecek veri kalmadi."
            return ReportGenerationResult(
                status="failed",
                report_type=report_type,
                audit_run_id=audit_run_id,
                message=error_message,
                errors=error_items,
                warnings=[coerce_warning_item(w) for w in (filter_warnings + validation["warnings"])],
                filter=filter_summary.model_dump(),
            )

        warnings_list += validation["warnings"]

        if validation.get("usable_row_count", 0) <= 0:
            return ReportGenerationResult(
                status="failed",
                report_type=report_type,
                audit_run_id=audit_run_id,
                message="Validation sonrasi rapor uretecek veri kalmadi.",
                warnings=[coerce_warning_item(w) for w in warnings_list],
                filter=filter_summary.model_dump(),
            )

        return generate_report_from_transactions(
            report_type=report_type,
            transactions=validation["transactions"],
            audit_run_id=audit_run_id,
            report_definition=report_definition,
            intent=intent,
            audit_context=audit_context,
            mapping_json=mapping_json,
            warnings_list=warnings_list,
            filter_summary=filter_summary.model_dump(),
            input_warnings=validation["warnings"],
            source_files=[file_path],
        )

    except Exception as e:
        logger.exception("Rapor uretimi sirasinda beklenmeyen hata.")
        return ReportGenerationResult(
            status="failed",
            report_type=report_type,
            audit_run_id=audit_run_id,
            message=f"Beklenmeyen internal hata: {str(e)}"
        )


def generate_report_from_normalized_dataframe(
    report_type: str,
    normalized_df: pd.DataFrame,
    audit_run_id: str,
    user_prompt: str | None = None,
    warnings_list: list[dict] | None = None,
    filter_summary: dict[str, Any] | None = None,
    source_files: list[str] | None = None,
) -> ReportGenerationResult:
    try:
        report_definition = REGISTRY.get_report_definition(report_type)
    except KeyError:
        return ReportGenerationResult(
            status="failed",
            report_type=report_type,
            audit_run_id=audit_run_id,
            message="Desteklenmeyen rapor tipi.",
        )

    intent = create_intent(
        report_type=report_type,
        input_type="excel",
        user_request=user_prompt or "",
    )
    audit_context = create_audit_context(report_definition)
    audit_context["audit_run_id"] = audit_run_id

    validation = validate_transactions(
        transactions=normalized_df.to_dict(orient="records"),
        report_definition=report_definition,
        filters={},
        audit_context=audit_context,
    )
    error_items = coerce_error_items(validation.get("errors"))
    if not validation["valid"] or validation.get("usable_row_count", 0) <= 0:
        message = error_items[0].get("message") if error_items else "Validation sonrasi rapor uretecek veri kalmadi."
        return ReportGenerationResult(
            status="failed",
            report_type=report_type,
            audit_run_id=audit_run_id,
            warnings=[coerce_warning_item(w) for w in (warnings_list or []) + validation.get("warnings", [])],
            errors=error_items,
            filter=filter_summary,
            message=message,
        )

    return generate_report_from_transactions(
        report_type=report_type,
        transactions=validation["transactions"],
        audit_run_id=audit_run_id,
        report_definition=report_definition,
        intent=intent,
        audit_context=audit_context,
        mapping_json=None,
        warnings_list=(warnings_list or []) + validation.get("warnings", []),
        filter_summary=filter_summary,
        input_warnings=validation.get("warnings", []),
        source_files=source_files,
    )


def generate_report_from_transactions(
    report_type: str,
    transactions: list[dict],
    audit_run_id: str,
    *,
    report_definition: dict,
    intent: dict,
    audit_context: dict,
    mapping_json: dict | None,
    warnings_list: list[dict] | None,
    filter_summary: dict[str, Any] | None,
    input_warnings: list[dict] | None,
    source_files: list[str] | None,
) -> ReportGenerationResult:
    report_result = generate_report(
        report_definition=report_definition,
        report_input=transactions,
        intent=intent,
        audit_context=audit_context,
        input_warnings=input_warnings,
    )
    filter_payload = filter_summary or build_default_filter_summary(None, len(transactions)).model_dump()
    report_result["filter"] = filter_payload
    report_result.setdefault("metadata", {})
    report_result["metadata"]["filter"] = filter_payload
    report_result["metadata"]["source_files"] = [Path(item).name for item in source_files or [] if item]

    working_warnings = list(warnings_list or [])
    try:
        analysis_result = AIAnalysisService().generate(report_definition, report_result)
        report_result["analysis"] = analysis_result.get("analysis") or ""
        if analysis_result.get("warnings"):
            for warning in analysis_result["warnings"]:
                working_warnings.append(
                    {
                        "type": "ai_analysis_warning",
                        "severity": "warning",
                        "message": warning,
                    }
                )
    except Exception as exc:
        logger.warning(f"AI analysis generation failed: {exc}")
        report_result["analysis"] = ""

    try:
        filter_model = FilterApplicationSummary(**filter_payload)
    except Exception:
        filter_model = build_default_filter_summary(None, len(transactions))
    report_result = append_filter_sheet(report_result, filter_model)

    output_result = generate_outputs(
        report_definition=report_definition,
        intent=intent,
        transactions=transactions,
        report_result=report_result,
        source_file=(source_files or [None])[0],
        source_files=source_files,
        mapping=mapping_json,
        warnings=working_warnings,
        audit_context=audit_context,
    )

    target_dir = StorageService.get_output_dir(audit_run_id)
    generated_excel_path = output_result["files"].get("xlsx") or output_result["files"].get("excel")
    final_excel_path = None

    if generated_excel_path and Path(generated_excel_path).exists():
        final_excel_path = target_dir / "report.xlsx"
        shutil.copy2(generated_excel_path, final_excel_path)
        final_excel_path = str(final_excel_path)

    warnings_output = []
    for warning in output_result.get("warnings", []):
        try:
            warnings_output.append(WarningItem(**warning))
        except Exception:
            warnings_output.append(
                WarningItem(
                    type=warning.get("type", "unknown"),
                    severity=warning.get("severity", "info"),
                    message=warning.get("message", "Bilinmeyen uyari"),
                )
            )

    status_result = "success"
    if warnings_output and report_result.get("status") != "failed":
        status_result = "warning"
    if report_result.get("status") == "failed":
        status_result = "failed"

    return ReportGenerationResult(
        status=status_result,
        report_type=report_type,
        audit_run_id=audit_run_id,
        output_file_path=final_excel_path,
        output_file_name="report.xlsx",
        summary=report_result.get("summary", {}),
        warnings=warnings_output,
        filter=filter_payload,
        message="Rapor basariyla uretildi." if status_result == "success" else "Rapor uretildi (uyarilar mevcut).",
    )


def resolve_date_bounds(df: pd.DataFrame, field_name: str | None) -> tuple[str | None, str | None]:
    if not field_name or field_name not in df.columns or df.empty:
        return None, None

    parsed_values = [
        parsed
        for parsed in df[field_name].map(lambda value: parse_date_value(value, timezone_value=None))
        if parsed is not None and not pd.isna(parsed)
    ]
    if not parsed_values:
        return None, None

    minimum = min(parsed_values).date().isoformat()
    maximum = max(parsed_values).date().isoformat()
    return minimum, maximum


def build_default_filter_summary(user_prompt: str | None, row_count: int) -> FilterApplicationSummary:
    return FilterApplicationSummary(
        applied=False,
        user_prompt=user_prompt.strip() if user_prompt and user_prompt.strip() else None,
        spec=None,
        summary_lines=[],
        input_row_count=row_count,
        filtered_row_count=row_count,
    )


def append_filter_sheet(report_result: dict, filter_summary: FilterApplicationSummary) -> dict:
    report_payload = dict(report_result)
    sheets = list(report_payload.get("sheets", []))
    sheets = [sheet for sheet in sheets if sheet.get("name") != "Rapor Filtreleri"]
    sheets.append({"name": "Rapor Filtreleri", "data": build_filter_sheet_rows(filter_summary)})
    report_payload["sheets"] = sheets
    return report_payload


def build_filter_sheet_rows(filter_summary: FilterApplicationSummary) -> list[dict]:
    rows = [
        {"Alan": "Kullanici Istegi", "Deger": filter_summary.user_prompt or "-"},
        {"Alan": "Filtre Uygulandi", "Deger": "Evet" if filter_summary.applied else "Hayir"},
        {"Alan": "Baslangic Satir Sayisi", "Deger": filter_summary.input_row_count},
        {"Alan": "Filtre Sonrasi Satir Sayisi", "Deger": filter_summary.filtered_row_count},
    ]

    spec = filter_summary.spec
    if spec and spec.date_range:
        rows.append({"Alan": "Tarih Alani", "Deger": spec.date_range.field or "-"})
        rows.append({"Alan": "Tarih Baslangic", "Deger": spec.date_range.start_date or "-"})
        rows.append({"Alan": "Tarih Bitis", "Deger": spec.date_range.end_date or "-"})

    if spec:
        for index, amount_filter in enumerate(spec.amount_filters, start=1):
            if amount_filter.operator == "between":
                value = f"{amount_filter.field} {amount_filter.min_value} - {amount_filter.max_value}"
            else:
                value = f"{amount_filter.field} {amount_filter.operator} {amount_filter.value}"
            rows.append({"Alan": f"Tutar Filtresi {index}", "Deger": value})

        for index, category_filter in enumerate(spec.category_filters, start=1):
            rows.append({"Alan": f"Kategori Filtresi {index}", "Deger": f"{category_filter.field}: {', '.join(category_filter.values)}"})

        for index, status_filter in enumerate(spec.status_filters, start=1):
            rows.append({"Alan": f"Durum Filtresi {index}", "Deger": f"{status_filter.field}: {', '.join(status_filter.values)}"})

        if spec.include_only_overdue:
            rows.append({"Alan": "Ek Filtre", "Deger": "Sadece vadesi gecmis kayitlar"})
        if spec.include_only_unpaid:
            rows.append({"Alan": "Ek Filtre", "Deger": "Sadece odenmemis kayitlar"})

    for index, line in enumerate(filter_summary.summary_lines, start=1):
        rows.append({"Alan": f"Ozet {index}", "Deger": line})

    return rows


def coerce_warning_item(payload) -> WarningItem:
    if isinstance(payload, WarningItem):
        return payload
    try:
        return WarningItem(**payload)
    except Exception:
        return WarningItem(
            type=getattr(payload, "get", lambda *_: "unknown")("type", "unknown") if hasattr(payload, "get") else "unknown",
            severity=getattr(payload, "get", lambda *_: "warning")("severity", "warning") if hasattr(payload, "get") else "warning",
            message=getattr(payload, "get", lambda *_: str(payload))("message", str(payload)) if hasattr(payload, "get") else str(payload),
        )


def coerce_error_items(payloads: list[Any] | None) -> list[dict[str, Any]]:
    if not payloads:
        return []
    return [coerce_error_item(payload) for payload in payloads]


def coerce_error_item(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    return {"message": str(payload)}
