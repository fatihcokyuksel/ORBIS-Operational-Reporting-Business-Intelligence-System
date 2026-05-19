from services.report.report_execution_service import ReportExecutionService
from services.report.report_registry_service import ReportRegistryService


_registry_service = ReportRegistryService()
_execution_service = ReportExecutionService(_registry_service)


def generate_report(
    report_definition: dict,
    report_input: list[dict],
    intent: dict | None = None,
    audit_context: dict | None = None,
    input_warnings: list[dict] | None = None,
) -> dict:
    return _execution_service.generate_report(
        report_definition=report_definition,
        report_input=report_input,
        intent=intent,
        audit_context=audit_context,
        input_warnings=input_warnings,
    )
