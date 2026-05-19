from pathlib import Path
from tkinter import Tk, filedialog
import json
import sys
import time

from agents.excel_parsing_agent import parse_excel_full
from agents.excel_preview_agent import create_excel_preview_json, save_preview_json
from agents.heuristic_mapping_agent import create_heuristic_mapping
from agents.llm_mapping_agent import create_mapping
from agents.prompt_parsing_agent import create_intent, extract_prompt_transactions
from agents.report_generator_agent import generate_report
from outputs.output_generator import generate_outputs
from services.report.report_execution_service import ReportExecutionService
from services.report.report_registry_service import ReportRegistryService
from services.report.report_suitability_service import (
    assess_excel_suitability,
    assess_input_support,
    mapping_references_existing_columns,
    normalized_payload_is_usable,
    assess_prompt_suitability,
)
from utils.audit_utils import create_audit_context
from utils.mapping_utils import sanitize_mapping_for_report
from validators.mapping_validator import validate_mapping_format
from validators.transaction_validator import validate_transactions


INPUT_TYPES = {
    1: "excel",
    2: "prompt",
}

REGISTRY = ReportRegistryService()
EXECUTION = ReportExecutionService(REGISTRY)


def select_file():
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Verilerinizi iceren Excel dosyasini seciniz.",
        filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
    )

    root.destroy()
    return file_path


def select_report_definition():
    reports = REGISTRY.list_reports()
    print("\nUretmek istediginiz raporu seciniz:\n")
    for number, definition in enumerate(reports, start=1):
        print(f"[{number}] {definition['display_name']}")

    try:
        selection = int(input(">>> ").strip())
    except ValueError:
        print("Lutfen sayi giriniz.")
        return None

    if selection < 1 or selection > len(reports):
        print("Gecersiz rapor secimi.")
        return None

    return reports[selection - 1]


def select_input_type(report_definition: dict):
    supported_inputs = report_definition.get("supported_inputs", [])
    print("\nVeri giris yontemini seciniz:\n")
    for number, input_type in INPUT_TYPES.items():
        if input_type in supported_inputs:
            label = "Excel dosyasi" if input_type == "excel" else "Dogal dil prompt"
            print(f"[{number}] {label}")

    try:
        selection = int(input(">>> ").strip())
    except ValueError:
        print("Lutfen sayi giriniz.")
        return None

    input_type = INPUT_TYPES.get(selection)
    if not input_type:
        print("Gecersiz veri giris tipi.")
        return None

    support_check = assess_input_support(report_definition, input_type, REGISTRY)
    if support_check["status"] != "passed":
        print_suitability_feedback(support_check)
        return None

    return input_type


def print_errors(title, errors):
    print(f"\n{title}")
    for error in errors:
        print(f"- {format_warning_for_cli(error)}")


def format_warning_for_cli(item) -> str:
    if not isinstance(item, dict):
        return str(item)
    severity = item.get("severity", "warning").upper()
    row = item.get("row")
    field = item.get("field")
    prefix = f"[{severity}]"
    if row:
        prefix += f" satir {row}"
    if field:
        prefix += f" alan {field}"
    return f"{prefix}: {item.get('message')}"


def print_suitability_feedback(suitability: dict):
    print("\nSecilen rapor bu veri girisi ile su an uretilemiyor.")
    if suitability.get("message"):
        print(suitability["message"])
    if suitability.get("missing_fields"):
        print_errors("Eksik alanlar:", suitability["missing_fields"])
    if suitability.get("available_alternative_reports"):
        print("\nBu verilerle su raporlar uretilebilir:")
        for report in suitability["available_alternative_reports"]:
            print(f"- {report['display_name']} ({report['report_id']})")


def run_excel_flow(report_definition: dict, user_request: str, intent: dict):
    print("\nLutfen Excel dosyasini secin...")
    time.sleep(0.5)

    file_path = select_file()
    if not file_path:
        print("Dosya secilmedi. Islem iptal edildi.")
        return None

    print("\n[1/7] Excel preview JSON olusturuluyor...")
    preview_json = create_excel_preview_json(file_path)
    save_preview_json(preview_json, "outputs/debug_outputs/excel_preview.json")

    report_id = report_definition["report_id"]

    print("\n[2/7] Mapping/context JSON uretiyor...")
    mapping_json = create_mapping(
        report_type=report_id,
        preview_json=preview_json,
        user_request=user_request,
    )
    mapping_json = sanitize_mapping_for_report(mapping_json, report_definition)

    validation_result = validate_mapping_format(
        report_type=report_id,
        mapping_json=mapping_json,
        report_definition=report_definition,
    )

    if not validation_result["valid"]:
        fallback_mapping = create_heuristic_mapping(
            report_type=report_id,
            preview_json=preview_json,
            reason="LLM mapping schema validation basarisiz oldu.",
        )
        fallback_mapping = sanitize_mapping_for_report(fallback_mapping, report_definition)
        fallback_validation = validate_mapping_format(
            report_type=report_id,
            mapping_json=fallback_mapping,
            report_definition=report_definition,
        )
        if fallback_validation["valid"]:
            mapping_json = fallback_mapping
            validation_result = fallback_validation

    if not validation_result["valid"]:
        print_errors("Mapping validation basarisiz:", validation_result["errors"])
        if validation_result["warnings"]:
            print_errors("Uyarilar:", validation_result["warnings"])
        return None

    column_reference_check = mapping_references_existing_columns(mapping_json, preview_json)
    if not column_reference_check["valid"]:
        fallback_mapping = create_heuristic_mapping(
            report_type=report_id,
            preview_json=preview_json,
            reason="LLM mapping preview kolonlariyla uyusmadi.",
        )
        fallback_mapping = sanitize_mapping_for_report(fallback_mapping, report_definition)
        fallback_validation = validate_mapping_format(
            report_type=report_id,
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
        print_suitability_feedback(suitability)
        return None

    if validation_result["warnings"] or mapping_json.get("warnings"):
        warnings = validation_result["warnings"] + mapping_json.get("warnings", [])
        print_errors("Mapping uyarilari:", warnings)

    print("\n[3/7] Excel full parse calisiyor...")
    raw_df = parse_excel_full(
        file_path=file_path,
        sheet_name=mapping_json["selected_sheet"],
    )

    print("\n[4/7] Rapora ozel veri kontratina normalize ediliyor...")
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
            report_type=report_id,
            preview_json=preview_json,
            reason="Ilk mapping normalize asamasinda kullanilabilir veri uretemedi.",
        )
        fallback_mapping = sanitize_mapping_for_report(fallback_mapping, report_definition)
        fallback_validation = validate_mapping_format(
            report_type=report_id,
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
        print("\nNormalize edilen veri secilen rapor icin anlamli bir direction yapisi uretemedi.")
        print("Farkli bir rapor secmeyi veya Excel kolonlarini daha acik hale getirmeyi deneyin.")
        return None

    return {
        "source_file": file_path,
        "mapping": mapping_json,
        "items": normalized_payload["items"],
        "warnings": mapping_json.get("warnings", []),
    }


def run_prompt_flow(report_definition: dict, user_request: str, intent: dict):
    print("\n[1/5] Prompt finansal veriye donusturuluyor...")
    extraction = extract_prompt_transactions(
        prompt=user_request,
        report_type=report_definition["report_id"],
        intent=intent,
    )

    suitability = assess_prompt_suitability(
        report_definition=report_definition,
        extraction_result=extraction,
        registry_service=REGISTRY,
    )
    if suitability["status"] != "passed":
        print_suitability_feedback(suitability)
        return None

    return {
        "source_file": None,
        "mapping": None,
        "items": extraction["transactions"],
        "warnings": extraction.get("warnings", []),
    }


def main():
    report_definition = select_report_definition()
    if report_definition is None:
        return

    input_type = select_input_type(report_definition)
    if input_type is None:
        return

    user_request = input(
        "\nRapor icin ozel isteginizi veya prompt verinizi yaziniz:\n>>> "
    ).strip()

    if input_type == "prompt" and not user_request:
        print("Prompt girisi icin metin gerekli.")
        return

    print("\n[Intent] Kullanici istegi sistem filtresine donusturuluyor...")
    intent = create_intent(
        report_type=report_definition["report_id"],
        input_type=input_type,
        user_request=user_request,
    )
    audit_context = create_audit_context(report_definition)

    if input_type == "excel":
        flow_result = run_excel_flow(report_definition, user_request, intent)
    else:
        flow_result = run_prompt_flow(report_definition, user_request, intent)

    if not flow_result:
        return

    print("\n[Validation] Normalize veri dogrulaniyor...")
    validation = validate_transactions(
        transactions=flow_result["items"],
        report_definition=report_definition,
        filters=intent.get("filters", {}),
        audit_context=audit_context,
    )

    if not validation["valid"]:
        print_errors("Veri validation basarisiz:", validation["errors"])
        if validation["warnings"]:
            print_errors("Uyarilar:", validation["warnings"])
        return

    if validation["warnings"]:
        print_errors("Veri uyarilari:", validation["warnings"])

    if validation.get("usable_row_count", 0) <= 0:
        print("\nValidation sonrasi rapor uretecek veri kalmadi.")
        return

    print("\n[Report] Rapor agenti secilen template ile raporu hazirliyor...")
    report_result = generate_report(
        report_definition=report_definition,
        report_input=validation["transactions"],
        intent=intent,
        audit_context=audit_context,
        input_warnings=validation["warnings"],
    )

    print("\n[Output] JSON + Excel + PNG olusturuluyor...")
    output_result = generate_outputs(
        report_definition=report_definition,
        intent=intent,
        transactions=validation["transactions"],
        report_result=report_result,
        source_file=flow_result["source_file"],
        mapping=flow_result["mapping"],
        warnings=flow_result["warnings"] + validation["warnings"],
        audit_context=audit_context,
    )

    print("\nIslem tamamlandi. Uretilen dosyalar:")
    for output_type, path in output_result["files"].items():
        print(f"- {output_type}: {Path(path).resolve()}")

    print("\nKisa ozet:")
    print(json.dumps(report_result["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nIslem kullanici tarafindan durduruldu.")
        sys.exit(130)
