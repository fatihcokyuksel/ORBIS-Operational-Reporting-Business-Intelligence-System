from __future__ import annotations

from importlib import import_module
from pathlib import Path
import json


class ReportRegistryService:
    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parents[2])
        self.index_path = self.base_dir / "reports" / "index.json"
        self._definitions = None

    def load_definitions(self) -> list[dict]:
        if self._definitions is not None:
            return self._definitions

        with self.index_path.open("r", encoding="utf-8") as file:
            index_payload = json.load(file)

        definitions = []
        seen_ids = set()
        for item in index_payload.get("reports", []):
            report_id = item["report_id"]
            if report_id in seen_ids:
                raise ValueError(f"Duplicate report_id bulundu: {report_id}")

            template_path = self.base_dir / item["template_path"]
            with template_path.open("r", encoding="utf-8") as file:
                definition = json.load(file)

            if definition.get("report_id") != report_id:
                raise ValueError(f"Index ve template report_id uyusmuyor: {report_id}")

            self.resolve_handler_class(definition["handler_class"])
            seen_ids.add(report_id)
            definitions.append(definition)

        self._definitions = definitions
        return definitions

    def list_reports(self, input_type: str | None = None) -> list[dict]:
        reports = self.load_definitions()
        if input_type is None:
            return reports
        return [report for report in reports if input_type in report.get("supported_inputs", [])]

    def get_report_definition(self, report_id: str) -> dict:
        for definition in self.load_definitions():
            if definition["report_id"] == report_id:
                return definition
        raise KeyError(f"Report tanimi bulunamadi: {report_id}")

    def get_alternative_reports(self, report_id: str) -> list[dict]:
        definition = self.get_report_definition(report_id)
        alternatives = []
        for alternative_id in definition.get("alternative_reports", []):
            alternatives.append(self.get_report_definition(alternative_id))
        return alternatives

    def resolve_handler_class(self, dotted_path: str):
        module_name, class_name = dotted_path.rsplit(".", 1)
        module = import_module(module_name)
        return getattr(module, class_name)
