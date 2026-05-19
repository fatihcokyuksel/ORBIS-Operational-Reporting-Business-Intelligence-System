from __future__ import annotations

import logging

import pandas as pd

from schemas.artifact_models import ArtifactGenerationResult, ArtifactInfo, UploadedFileInfo
from services.analysis.analysis_generation_service import generate_analysis_artifact
from services.artifact_catalog import ANALYSIS_DEFINITIONS, CHART_DEFINITIONS
from services.chart.chart_generation_service import generate_chart_artifact
from services.multi_file_normalization_service import normalize_multiple_excel_files
from services.report.prompt_data_extraction_service import extract_chart_data_from_prompt
from services.report.report_generation_service import (
    build_default_filter_summary,
    coerce_warning_item,
    generate_report_from_normalized_dataframe,
)
from services.report.report_registry_service import ReportRegistryService
from services.storage_service import StorageService


logger = logging.getLogger(__name__)

REGISTRY = ReportRegistryService()


def list_all_artifacts() -> list[ArtifactInfo]:
    artifacts: list[ArtifactInfo] = []
    for report_def in REGISTRY.list_reports():
        artifacts.append(
            ArtifactInfo(
                artifact_type="report",
                artifact_id=report_def["report_id"],
                display_name=report_def["display_name"],
                output_format="xlsx",
                supported_input=list(report_def.get("supported_inputs", ["excel"])),
            )
        )
    for chart_def in CHART_DEFINITIONS.values():
        artifacts.append(
            ArtifactInfo(
                artifact_type="chart",
                artifact_id=chart_def.artifact_id,
                display_name=chart_def.display_name,
                output_format="jpg",
                supported_input=chart_def.supported_input,
            )
        )
    for analysis_def in ANALYSIS_DEFINITIONS.values():
        artifacts.append(
            ArtifactInfo(
                artifact_type="analysis",
                artifact_id=analysis_def.artifact_id,
                display_name=analysis_def.display_name,
                output_format="pdf",
                supported_input=analysis_def.supported_input,
            )
        )
    return artifacts


def generate_artifact(
    artifact_type: str,
    artifact_id: str,
    audit_run_id: str,
    file_path: str | None = None,
    file_paths: list[str] | None = None,
    output_format: str | None = None,
    user_prompt: str | None = None,
) -> ArtifactGenerationResult:
    resolved_paths = [item for item in (file_paths or []) if item]
    if file_path:
        resolved_paths.insert(0, file_path)

    if artifact_type == "report":
        return _generate_report_artifact(artifact_id, audit_run_id, resolved_paths, output_format, user_prompt)
    if artifact_type == "chart":
        return _generate_chart_artifact(artifact_id, audit_run_id, resolved_paths, user_prompt)
    if artifact_type == "analysis":
        return _generate_analysis_artifact(artifact_id, audit_run_id, resolved_paths, user_prompt)
    return ArtifactGenerationResult(
        status="failed",
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        audit_run_id=audit_run_id,
        output_format=output_format or "unknown",
        message="Desteklenmeyen artifact tipi.",
    )


def _generate_report_artifact(
    report_type: str,
    audit_run_id: str,
    file_paths: list[str],
    output_format: str | None,
    user_prompt: str | None,
) -> ArtifactGenerationResult:
    if not file_paths:
        return ArtifactGenerationResult(
            status="failed",
            artifact_type="report",
            artifact_id=report_type,
            audit_run_id=audit_run_id,
            output_format=output_format or "xlsx",
            message="Excel raporu icin en az bir .xlsx dosyasi zorunludur.",
        )

    normalization = normalize_multiple_excel_files(
        files=[UploadedFileInfo(file_name=_file_name(path), file_path=path) for path in file_paths],
        artifact_id=report_type,
        artifact_type="report",
        user_prompt=user_prompt,
        audit_run_id=audit_run_id,
    )
    if normalization.status == "failed":
        return ArtifactGenerationResult(
            status="failed",
            artifact_type="report",
            artifact_id=report_type,
            audit_run_id=audit_run_id,
            output_format=output_format or "xlsx",
            warnings=[coerce_warning_item(item) for item in normalization.warnings],
            filter_summary=normalization.filter_summary,
            message="Gecerli Excel verisi olusturulamadi.",
        )

    report_result = generate_report_from_normalized_dataframe(
        report_type=report_type,
        normalized_df=pd.DataFrame(normalization.normalized_records),
        audit_run_id=audit_run_id,
        user_prompt=user_prompt,
        warnings_list=normalization.warnings,
        filter_summary=normalization.filter_summary,
        source_files=file_paths,
    )
    return ArtifactGenerationResult(
        status=report_result.status,
        artifact_type="report",
        artifact_id=report_result.report_type,
        audit_run_id=report_result.audit_run_id,
        output_file_path=report_result.output_file_path,
        output_file_name=report_result.output_file_name,
        output_format=output_format or "xlsx",
        summary=report_result.summary,
        warnings=report_result.warnings,
        errors=report_result.errors,
        filter_summary=report_result.filter,
        message=report_result.message,
    )


def _generate_chart_artifact(
    artifact_id: str,
    audit_run_id: str,
    file_paths: list[str],
    user_prompt: str | None,
) -> ArtifactGenerationResult:
    chart_def = CHART_DEFINITIONS.get(artifact_id)
    if chart_def is None:
        return ArtifactGenerationResult(
            status="failed",
            artifact_type="chart",
            artifact_id=artifact_id,
            audit_run_id=audit_run_id,
            output_format="jpg",
            message="Desteklenmeyen grafik tipi.",
        )

    try:
        if file_paths:
            normalization = normalize_multiple_excel_files(
                files=[UploadedFileInfo(file_name=_file_name(path), file_path=path) for path in file_paths],
                artifact_id=artifact_id,
                artifact_type="chart",
                user_prompt=user_prompt,
                audit_run_id=audit_run_id,
            )
            if normalization.status == "failed":
                return ArtifactGenerationResult(
                    status="failed",
                    artifact_type="chart",
                    artifact_id=artifact_id,
                    audit_run_id=audit_run_id,
                    output_format="jpg",
                    warnings=[coerce_warning_item(item) for item in normalization.warnings],
                    filter_summary=normalization.filter_summary,
                    message="Grafik icin kullanilabilir veri kalmadi.",
                )
            df = pd.DataFrame(normalization.normalized_records)
            warnings = normalization.warnings
            filter_summary = normalization.filter_summary
        elif user_prompt and "prompt" in chart_def.supported_input:
            df, warnings, filter_summary = _prepare_dataframe_from_prompt(artifact_id, user_prompt)
        else:
            return ArtifactGenerationResult(
                status="failed",
                artifact_type="chart",
                artifact_id=artifact_id,
                audit_run_id=audit_run_id,
                output_format="jpg",
                message="Bu grafik icin Excel dosyasi veya desteklenen prompt verisi gereklidir.",
            )

        output_dir = StorageService.get_output_dir(audit_run_id)
        generation = generate_chart_artifact(artifact_id, df, output_dir, user_prompt=user_prompt)
        warnings_output = [coerce_warning_item(item) for item in warnings]
        status = "warning" if warnings_output else "success"
        return ArtifactGenerationResult(
            status=status,
            artifact_type="chart",
            artifact_id=artifact_id,
            audit_run_id=audit_run_id,
            output_file_path=generation["output_file_path"],
            output_file_name=generation["output_file_name"],
            output_format="jpg",
            summary=generation.get("summary", {}),
            warnings=warnings_output,
            filter_summary=filter_summary,
            message="Grafik hazir." if status == "success" else "Grafik hazir, bazi uyarilar mevcut.",
        )
    except Exception as exc:
        logger.exception("Grafik uretimi basarisiz")
        return ArtifactGenerationResult(
            status="failed",
            artifact_type="chart",
            artifact_id=artifact_id,
            audit_run_id=audit_run_id,
            output_format="jpg",
            message=str(exc),
        )


def _generate_analysis_artifact(
    artifact_id: str,
    audit_run_id: str,
    file_paths: list[str],
    user_prompt: str | None,
) -> ArtifactGenerationResult:
    if artifact_id not in ANALYSIS_DEFINITIONS:
        return ArtifactGenerationResult(
            status="failed",
            artifact_type="analysis",
            artifact_id=artifact_id,
            audit_run_id=audit_run_id,
            output_format="pdf",
            message="Desteklenmeyen analiz tipi.",
        )
    if not file_paths:
        return ArtifactGenerationResult(
            status="failed",
            artifact_type="analysis",
            artifact_id=artifact_id,
            audit_run_id=audit_run_id,
            output_format="pdf",
            message="Analiz raporu icin en az bir .xlsx dosyasi zorunludur.",
        )

    try:
        normalization = normalize_multiple_excel_files(
            files=[UploadedFileInfo(file_name=_file_name(path), file_path=path) for path in file_paths],
            artifact_id=artifact_id,
            artifact_type="analysis",
            user_prompt=user_prompt,
            audit_run_id=audit_run_id,
        )
        if normalization.status == "failed":
            return ArtifactGenerationResult(
                status="failed",
                artifact_type="analysis",
                artifact_id=artifact_id,
                audit_run_id=audit_run_id,
                output_format="pdf",
                warnings=[coerce_warning_item(item) for item in normalization.warnings],
                filter_summary=normalization.filter_summary,
                message="Analiz icin kullanilabilir veri kalmadi.",
            )

        output_dir = StorageService.get_output_dir(audit_run_id)
        generation = generate_analysis_artifact(
            artifact_id,
            pd.DataFrame(normalization.normalized_records),
            output_dir,
            user_prompt=user_prompt,
            source_files=file_paths,
            warnings=normalization.warnings,
            filter_summary=normalization.filter_summary,
        )
        warnings_output = [coerce_warning_item(item) for item in normalization.warnings]
        status = "warning" if warnings_output else "success"
        return ArtifactGenerationResult(
            status=status,
            artifact_type="analysis",
            artifact_id=artifact_id,
            audit_run_id=audit_run_id,
            output_file_path=generation["output_file_path"],
            output_file_name=generation["output_file_name"],
            output_format="pdf",
            summary=generation.get("summary", {}),
            warnings=warnings_output,
            filter_summary=normalization.filter_summary,
            message="Analiz raporu hazir." if status == "success" else "Analiz raporu hazir, bazi uyarilar mevcut.",
        )
    except Exception as exc:
        logger.exception("Analiz uretimi basarisiz")
        return ArtifactGenerationResult(
            status="failed",
            artifact_type="analysis",
            artifact_id=artifact_id,
            audit_run_id=audit_run_id,
            output_format="pdf",
            message=str(exc),
        )


def _prepare_dataframe_from_prompt(artifact_id: str, user_prompt: str):
    records = extract_chart_data_from_prompt(user_prompt, artifact_id)
    if not records:
        raise ValueError("Prompt icinden grafik icin kullanilabilir yapisal veri cikarilamadi.")
    df = pd.DataFrame(records)
    if {"income", "expense"}.issubset(df.columns):
        exploded = []
        for _, row in df.iterrows():
            period = row.get("period")
            income = float(row.get("income", 0) or 0)
            expense = float(row.get("expense", 0) or 0)
            exploded.append({"period": period, "direction": "income", "amount": income, "income": income, "expense": expense})
            exploded.append({"period": period, "direction": "expense", "amount": expense, "income": income, "expense": expense})
        df = pd.DataFrame(exploded)
    filter_summary = build_default_filter_summary(user_prompt, len(df)).model_dump()
    filter_summary["applied"] = False
    return df, [], filter_summary


def _file_name(path: str) -> str:
    return path.split("/")[-1].split("\\")[-1]
