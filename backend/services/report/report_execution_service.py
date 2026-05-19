from __future__ import annotations

import pandas as pd

from normalizers.transaction_normalizer import normalize_excel_dataframe
from utils.audit_utils import ensure_audit_context
from utils.mapping_utils import sanitize_mapping_for_report
from utils.warning_utils import determine_execution_status, summarize_warning_severity, unique_warnings


class ReportExecutionService:
    def __init__(self, registry_service):
        self.registry_service = registry_service

    def normalize_for_report(self, report_definition: dict, raw_data, mapping_json: dict, intent: dict) -> dict:
        mapping_json = sanitize_mapping_for_report(mapping_json, report_definition)
        agent_class = self.registry_service.resolve_handler_class(report_definition["handler_class"])
        agent = agent_class(report_definition)

        if hasattr(agent, "normalize"):
            items = agent.normalize(pd.DataFrame(raw_data), mapping_json)
            return {
                "report_id": report_definition["report_id"],
                "model_type": report_definition["input_contract"]["model_type"],
                "items": items,
            }

        family = report_definition.get("family")
        if family == "transaction":
            items = normalize_excel_dataframe(
                df=raw_data,
                mapping_json=mapping_json,
                report_type=report_definition["report_id"],
                intent=intent,
            )
            return {
                "report_id": report_definition["report_id"],
                "model_type": report_definition["input_contract"]["model_type"],
                "items": items,
            }

        raise ValueError(f"Desteklenmeyen report family: {family}")

    def generate_report(
        self,
        report_definition: dict,
        report_input: list[dict],
        intent: dict | None = None,
        audit_context: dict | None = None,
        input_warnings: list[dict] | None = None,
    ) -> dict:
        context = ensure_audit_context(audit_context, report_definition)
        handler_class = self.registry_service.resolve_handler_class(report_definition["handler_class"])
        handler = handler_class(report_definition)

        if hasattr(handler, "generate") and not hasattr(handler, "compute"):
            if not report_input:
                raise ValueError("Validation sonrasi rapor uretecek veri kalmadi.")
            validation = handler.validate(pd.DataFrame(report_input), audit_context=context)
            if validation.get("status") == "failed":
                raise ValueError(validation.get("message") or "Rapor girdisi uygun degil.")
            report_result = handler.generate(validation["dataframe"], output_path=None, audit_context=context)
            report_result["warnings"] = unique_warnings(
                report_result.get("warnings", []) + validation.get("warnings", []) + (input_warnings or []),
                context,
            )
            report_result.setdefault("summary", {})
            report_result["summary"]["warning_count"] = len(report_result["warnings"])
            report_result["summary"]["dropped_row_count"] = sum(1 for warning in report_result["warnings"] if warning.get("action") == "row_dropped")
            report_result["summary"]["recalculated_field_count"] = sum(1 for warning in report_result["warnings"] if warning.get("action") == "used_calculated_value")
            report_result["warning_summary"] = summarize_warning_severity(report_result["warnings"])
            report_result.setdefault("metadata", validation.get("metadata", {}))
            report_result["execution_status"] = determine_execution_status(report_result["warnings"])
            return report_result

        applicability = handler.check_applicability(report_input, intent)
        if applicability.get("status") != "passed":
            raise ValueError(applicability.get("message") or "Rapor girdisi uygun degil.")

        computed_report = handler.compute(report_input, intent)
        rendered_payload = handler.render_payload(computed_report)
        rendered_payload["warnings"] = unique_warnings(
            rendered_payload.get("warnings", []) + applicability.get("warnings", []) + (input_warnings or []),
            context,
        )
        rendered_payload["warning_summary"] = summarize_warning_severity(rendered_payload["warnings"])
        rendered_payload["execution_status"] = determine_execution_status(rendered_payload["warnings"])
        rendered_payload.setdefault("metadata", context)
        return rendered_payload
