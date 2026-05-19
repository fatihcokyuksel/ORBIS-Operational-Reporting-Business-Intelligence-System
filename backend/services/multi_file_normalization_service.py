from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from agents.excel_parsing_agent import parse_excel_full
from agents.excel_preview_agent import create_excel_preview_json
from agents.heuristic_mapping_agent import create_heuristic_mapping
from agents.llm_mapping_agent import create_mapping
from agents.prompt_parsing_agent import create_intent
from schemas.artifact_models import FileNormalizationSummary, MultiFileNormalizeResult, UploadedFileInfo
from services.artifact_catalog import ANALYSIS_DEFINITIONS, CHART_DEFINITIONS
from services.report.report_execution_service import ReportExecutionService
from services.report.report_filter_defaults import get_report_filter_defaults
from services.report.report_filter_engine import apply_report_filters
from services.report.report_generation_service import build_default_filter_summary, resolve_date_bounds
from services.report.report_prompt_filter_service import extract_report_filters
from services.report.report_registry_service import ReportRegistryService
from services.report.report_suitability_service import (
    assess_excel_suitability,
    mapping_references_existing_columns,
    normalized_payload_is_usable,
)
from utils.audit_utils import create_audit_context
from utils.mapping_utils import sanitize_mapping_for_report
from utils.warning_utils import append_invalid_value_warning
from validators.mapping_validator import validate_mapping_format


REGISTRY = ReportRegistryService()
EXECUTION = ReportExecutionService(REGISTRY)


def normalize_multiple_excel_files(
    files: list[UploadedFileInfo],
    artifact_id: str,
    artifact_type: str,
    user_prompt: str | None = None,
    audit_run_id: str | None = None,
) -> MultiFileNormalizeResult:
    source_report_type = resolve_source_report_type(artifact_type=artifact_type, artifact_id=artifact_id)
    summaries: list[FileNormalizationSummary] = []
    warnings: list[dict] = []
    normalized_frames: list[pd.DataFrame] = []
    input_row_count = 0

    for file_info in files:
        if not file_info.file_name.lower().endswith(".xlsx"):
            warning = {
                "type": "unsupported_file_type",
                "severity": "warning",
                "message": f"{file_info.file_name} dosyasi atlandi. Yalnizca .xlsx desteklenir.",
                "action": "file_skipped",
            }
            warnings.append(warning)
            summaries.append(
                FileNormalizationSummary(
                    file_name=file_info.file_name,
                    status="failed",
                    warnings=[warning],
                )
            )
            continue

        try:
            single_result = _normalize_single_excel_file(
                report_type=source_report_type,
                file_info=file_info,
                user_prompt=user_prompt,
                audit_run_id=audit_run_id,
            )
            input_row_count += single_result["raw_row_count"]
            normalized_frames.append(single_result["dataframe"])
            warnings.extend(single_result["warnings"])
            summaries.append(
                FileNormalizationSummary(
                    file_name=file_info.file_name,
                    status="warning" if single_result["warnings"] else "success",
                    raw_row_count=single_result["raw_row_count"],
                    normalized_row_count=len(single_result["dataframe"]),
                    mapped_fields=single_result["mapped_fields"],
                    warnings=single_result["warnings"],
                )
            )
        except Exception as exc:
            warning = {
                "type": "file_normalization_failed",
                "severity": "warning",
                "message": f"{file_info.file_name} normalize edilemedi: {exc}",
                "action": "file_skipped",
            }
            warnings.append(warning)
            summaries.append(
                FileNormalizationSummary(
                    file_name=file_info.file_name,
                    status="failed",
                    warnings=[warning],
                )
            )

    if not normalized_frames:
        return MultiFileNormalizeResult(
            status="failed",
            file_summaries=summaries,
            warnings=warnings,
            input_row_count=input_row_count,
            normalized_row_count=0,
            filter_summary=build_default_filter_summary(user_prompt, 0).model_dump(),
            source_report_type=source_report_type,
        )

    merged_df = pd.concat(normalized_frames, ignore_index=True, sort=False)
    deduplicated_df, duplicate_warning = _drop_exact_duplicates(merged_df)
    if duplicate_warning:
        warnings.append(duplicate_warning)

    filter_summary = build_default_filter_summary(user_prompt, len(deduplicated_df))
    filtered_df = deduplicated_df.copy()
    if user_prompt and user_prompt.strip():
        defaults = get_report_filter_defaults(source_report_type)
        min_date, max_date = resolve_date_bounds(deduplicated_df, defaults.get("primary_date_field"))
        filter_spec = extract_report_filters(
            user_prompt=user_prompt,
            report_type=source_report_type,
            available_columns=list(deduplicated_df.columns),
            normalized_schema=list(deduplicated_df.columns),
            min_date=min_date,
            max_date=max_date,
        )
        filtered_df, filter_warnings, filter_summary = apply_report_filters(
            deduplicated_df,
            filter_spec=filter_spec,
            report_type=source_report_type,
            user_prompt=user_prompt.strip(),
        )
        warnings.extend(filter_warnings)
        if not filter_spec.has_actionable_filters():
            append_invalid_value_warning(
                warnings,
                warning_type="filter_low_confidence",
                severity="warning",
                action="filter_not_applied",
                message="Kullanici isteginden uygulanabilir filtre cikarilamadi. Tum birlesik veri kullanildi.",
                context={"confidence": filter_spec.confidence, "notes": filter_spec.notes},
            )

    if filtered_df.empty:
        return MultiFileNormalizeResult(
            status="failed",
            file_summaries=summaries,
            warnings=warnings,
            input_row_count=input_row_count,
            normalized_row_count=0,
            filter_summary=filter_summary.model_dump(),
            source_report_type=source_report_type,
        )

    status = "warning" if any(summary.status != "success" for summary in summaries) or warnings else "success"
    return MultiFileNormalizeResult(
        status=status,
        normalized_records=filtered_df.where(pd.notna(filtered_df), None).to_dict(orient="records"),
        file_summaries=summaries,
        warnings=warnings,
        input_row_count=input_row_count,
        normalized_row_count=len(filtered_df),
        filter_summary=filter_summary.model_dump(),
        source_report_type=source_report_type,
    )


def resolve_source_report_type(artifact_type: str, artifact_id: str) -> str:
    if artifact_type == "report":
        return artifact_id
    if artifact_type == "chart":
        definition = CHART_DEFINITIONS.get(artifact_id)
        if definition is None:
            raise ValueError(f"Desteklenmeyen grafik tipi: {artifact_id}")
        return definition.source_report_type
    if artifact_type == "analysis":
        definition = ANALYSIS_DEFINITIONS.get(artifact_id)
        if definition is None:
            raise ValueError(f"Desteklenmeyen analiz tipi: {artifact_id}")
        return definition.source_report_type
    raise ValueError(f"Desteklenmeyen artifact tipi: {artifact_type}")


def _normalize_single_excel_file(
    report_type: str,
    file_info: UploadedFileInfo,
    user_prompt: str | None = None,
    audit_run_id: str | None = None,
) -> dict:
    report_definition = REGISTRY.get_report_definition(report_type)
    intent = create_intent(report_type=report_type, input_type="excel", user_request=user_prompt or "")
    audit_context = create_audit_context(report_definition)
    if audit_run_id:
        audit_context["audit_run_id"] = audit_run_id

    preview_json = create_excel_preview_json(file_info.file_path)
    mapping_json = create_mapping(report_type=report_type, preview_json=preview_json, user_request=user_prompt or "")
    mapping_json = sanitize_mapping_for_report(mapping_json, report_definition)
    validation_result = validate_mapping_format(
        report_type=report_type,
        mapping_json=mapping_json,
        report_definition=report_definition,
    )
    if not validation_result["valid"]:
        mapping_json = sanitize_mapping_for_report(
            create_heuristic_mapping(
                report_type=report_type,
                preview_json=preview_json,
                reason="LLM mapping validation basarisiz.",
            ),
            report_definition,
        )
        validation_result = validate_mapping_format(
            report_type=report_type,
            mapping_json=mapping_json,
            report_definition=report_definition,
        )
    if not validation_result["valid"]:
        raise ValueError("Mapping validation basarisiz.")

    if not mapping_references_existing_columns(mapping_json, preview_json)["valid"]:
        fallback_mapping = sanitize_mapping_for_report(
            create_heuristic_mapping(
                report_type=report_type,
                preview_json=preview_json,
                reason="Kolon eslemesi preview ile uyusmadi.",
            ),
            report_definition,
        )
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
        raise ValueError(suitability.get("message") or "Veri bu artifact icin uygun degil.")

    raw_df = parse_excel_full(file_path=file_info.file_path, sheet_name=mapping_json["selected_sheet"])
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
        raise ValueError("Normalize edilen veri artifact icin kullanilabilir degil.")

    field_mappings = mapping_json.get("field_mappings", {})
    mapped_fields = [
        field_name
        for field_name, mapping in field_mappings.items()
        if isinstance(mapping, dict) and mapping.get("mapping_type") not in {None, "not_available"}
    ]
    warnings = list(validation_result["warnings"]) + _coerce_mapping_warnings(mapping_json.get("warnings", []))
    return {
        "dataframe": pd.DataFrame(normalized_payload["items"]),
        "raw_row_count": len(raw_df),
        "mapped_fields": mapped_fields,
        "warnings": warnings,
    }


def _coerce_mapping_warnings(payload: list) -> list[dict]:
    warnings: list[dict] = []
    for item in payload or []:
        if isinstance(item, dict):
            warnings.append(item)
            continue
        warnings.append(
            {
                "type": "mapping_warning",
                "severity": "info",
                "message": str(item),
            }
        )
    return warnings


def _drop_exact_duplicates(df: pd.DataFrame) -> tuple[pd.DataFrame, dict | None]:
    if df.empty:
        return df, None

    fingerprint_series = df.apply(_stable_row_fingerprint, axis=1)
    duplicate_mask = fingerprint_series.duplicated(keep="first")
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count <= 0:
        return df, None

    deduplicated = df.loc[~duplicate_mask].reset_index(drop=True)
    warning = {
        "type": "duplicate_rows_dropped",
        "severity": "warning",
        "message": f"{duplicate_count} adet birebir tekrar eden kayit birlesim sonrasi kaldirildi.",
        "action": "rows_deduplicated",
        "context": {
            "duplicate_row_count": duplicate_count,
            "remaining_row_count": len(deduplicated),
        },
    }
    return deduplicated, warning


def _stable_row_fingerprint(row: pd.Series) -> str:
    normalized = {}
    for key, value in row.items():
        if pd.isna(value):
            normalized[key] = None
        elif isinstance(value, (pd.Timestamp, Path)):
            normalized[key] = str(value)
        else:
            normalized[key] = value
    return json.dumps(normalized, ensure_ascii=False, sort_keys=True, default=str)
