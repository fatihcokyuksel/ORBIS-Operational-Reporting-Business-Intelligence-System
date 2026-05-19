from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from utils.audit_utils import ensure_audit_context, make_metadata
from utils.excel_writer import write_report_workbook
from utils.mapping_utils import normalize_dataframe_for_report
from utils.validation import ROW_TRACKING_COLUMN
from utils.warning_utils import (
    determine_execution_status,
    legacy_status_from_execution,
    summarize_warning_severity,
    unique_warnings,
)


class BaseReportAgent(ABC):
    required_fields: list[str] = []
    optional_fields: list[str] = []
    numeric_fields: list[str] = []
    date_fields: list[str] = []
    duplicate_subset: list[str] = []

    def __init__(self, report_definition: dict):
        self.report_definition = report_definition

    @property
    def report_id(self) -> str:
        return self.report_definition["report_id"]

    @property
    def all_fields(self) -> list[str]:
        return list(dict.fromkeys(self.required_fields + self.optional_fields))

    def normalize(self, df: pd.DataFrame, mapping: dict) -> list[dict]:
        normalized_df = normalize_dataframe_for_report(
            df=df,
            mapping_json=mapping,
            report_definition=self.report_definition,
            numeric_fields=self.numeric_fields,
            date_fields=self.date_fields,
        )
        return normalized_df.to_dict(orient="records")

    @abstractmethod
    def validate(self, df: pd.DataFrame, audit_context: dict | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def generate(self, df: pd.DataFrame, output_path: str | None = None, audit_context: dict | None = None) -> dict:
        raise NotImplementedError

    def export_excel(self, result: dict, output_path: str):
        write_report_workbook(output_path, result.get("sheets", []), report_currency=result.get("metadata", {}).get("reporting_currency"))

    def finalize_validation_result(
        self,
        *,
        dataframe: pd.DataFrame,
        warnings: list[dict],
        audit_context: dict | None,
        missing_fields: list[str] | None = None,
        message: str | None = None,
    ) -> dict:
        context = ensure_audit_context(audit_context, self.report_definition)
        prepared_df = dataframe.copy()
        if ROW_TRACKING_COLUMN in prepared_df.columns:
            prepared_df = prepared_df.drop(columns=[ROW_TRACKING_COLUMN])
        prepared_df.attrs["warnings"] = unique_warnings(warnings, context)
        prepared_df.attrs["audit_context"] = context

        execution_status = determine_execution_status(prepared_df.attrs["warnings"])
        status = "failed" if execution_status == "failed" and prepared_df.empty else legacy_status_from_execution(execution_status)
        return {
            "status": status,
            "execution_status": execution_status,
            "report_type": self.report_id,
            "dataframe": prepared_df,
            "missing_fields": missing_fields or [],
            "warnings": prepared_df.attrs["warnings"],
            "warning_summary": summarize_warning_severity(prepared_df.attrs["warnings"]),
            "message": message,
            "metadata": make_metadata(self.report_definition, context),
        }

    def build_result(
        self,
        *,
        df: pd.DataFrame,
        summary: dict,
        tables: dict,
        sheets: list[dict],
        warnings: list[dict] | None = None,
        analysis_context: dict | None = None,
    ) -> dict:
        audit_context = ensure_audit_context(df.attrs.get("audit_context"), self.report_definition)
        result_warnings = unique_warnings(warnings or df.attrs.get("warnings", []), audit_context)
        sheet_statuses = [{"name": sheet.get("name"), "status": "success", "warnings": []} for sheet in sheets]
        execution_status = determine_execution_status(result_warnings, has_partial_sheet=any(item["status"] != "success" for item in sheet_statuses))
        summary_payload = dict(summary)
        summary_payload.setdefault("warning_count", len(result_warnings))
        summary_payload.setdefault(
            "dropped_row_count",
            sum(1 for warning in result_warnings if warning.get("action") == "row_dropped"),
        )
        summary_payload.setdefault(
            "recalculated_field_count",
            sum(1 for warning in result_warnings if warning.get("action") == "used_calculated_value"),
        )
        metadata_context = dict(audit_context)
        if summary_payload.get("reporting_currency"):
            metadata_context["reporting_currency"] = summary_payload["reporting_currency"]

        return {
            "status": legacy_status_from_execution(execution_status),
            "execution_status": execution_status,
            "report_type": self.report_id,
            "summary": summary_payload,
            "tables": tables,
            "sheets": sheets,
            "warnings": result_warnings,
            "warning_summary": summarize_warning_severity(result_warnings),
            "sheet_statuses": sheet_statuses,
            "metadata": make_metadata(self.report_definition, metadata_context),
            "analysis_context": analysis_context or {"summary": summary_payload},
        }
