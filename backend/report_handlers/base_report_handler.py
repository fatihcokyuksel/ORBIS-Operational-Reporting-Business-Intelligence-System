from __future__ import annotations

from abc import ABC, abstractmethod


REPORT_CONTRACT_KEYS = ["summary", "metrics", "tables", "charts", "analysis_context"]


class BaseReportHandler(ABC):
    def __init__(self, report_definition: dict):
        self.report_definition = report_definition

    def check_applicability(self, normalized_payload: list[dict], intent: dict | None = None) -> dict:
        return {
            "status": "passed",
            "warnings": [],
            "message": None,
        }

    @abstractmethod
    def compute(self, report_input: list[dict], intent: dict | None = None) -> dict:
        raise NotImplementedError

    def render_payload(self, computed_report: dict) -> dict:
        summary = computed_report.get("summary", {})
        metrics = computed_report.get("metrics") or self.build_metrics(summary)
        analysis_context = computed_report.get("analysis_context") or self.build_analysis_context(summary, metrics)

        return {
            "report_id": self.report_definition["report_id"],
            "summary": summary,
            "metrics": metrics,
            "tables": computed_report.get("tables", {}),
            "charts": computed_report.get("charts", []),
            "analysis_context": analysis_context,
            "narrative": computed_report.get("narrative"),
            "warnings": computed_report.get("warnings", []),
        }

    def build_metrics(self, summary: dict) -> list[dict]:
        metric_definitions = self.report_definition.get("output_config", {}).get("metrics", [])
        if not metric_definitions:
            metric_definitions = legacy_metric_definitions(self.report_definition)

        metrics = []
        for definition in metric_definitions:
            key = definition.get("key") or definition.get("summary_key")
            metrics.append(
                {
                    "key": key,
                    "label": definition.get("label") or key,
                    "value": summary.get(key),
                    "type": definition.get("type") or definition.get("value_type") or "currency",
                    "style": definition.get("style") or "neutral",
                }
            )
        return metrics

    def build_analysis_context(self, summary: dict, metrics: list[dict]) -> dict:
        return {
            "report_id": self.report_definition["report_id"],
            "report_name": self.report_definition.get("display_name"),
            "summary": summary,
            "metrics": [
                {
                    "key": metric.get("key"),
                    "label": metric.get("label"),
                    "value": metric.get("value"),
                    "type": metric.get("type"),
                }
                for metric in metrics
            ],
        }


def legacy_metric_definitions(report_definition: dict) -> list[dict]:
    output_config = report_definition.get("output_config", {})
    seen = set()
    definitions = []

    for source_key in ["metric_cards", "overview_rows"]:
        for item in output_config.get(source_key, []):
            key = item.get("summary_key")
            if not key or key in seen:
                continue
            seen.add(key)
            definitions.append(
                {
                    "key": key,
                    "label": item.get("label") or key,
                    "type": item.get("value_type") or style_to_type(item.get("style")),
                    "style": item.get("style") or "neutral",
                }
            )

    return definitions


def style_to_type(style: str | None) -> str:
    if style == "count":
        return "count"
    return "currency"
