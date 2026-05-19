from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.report_generator_agent import generate_report
from outputs.output_generator import generate_outputs
from services.report.report_registry_service import ReportRegistryService
from validators.transaction_validator import validate_transactions


SAMPLE_TRANSACTIONS = [
    {
        "date": "2026-05-01",
        "description": "Satış tahsilatı",
        "amount": 12000.0,
        "direction": "income",
        "balance": 52000.0,
        "counterparty": "A Firması",
        "category": "Satış",
        "currency": "TRY",
        "source": "excel",
    },
    {
        "date": "2026-05-02",
        "description": "Kira ödemesi",
        "amount": 3500.0,
        "direction": "expense",
        "category": "Kira",
        "currency": "TRY",
        "source": "excel",
    },
    {
        "date": "2026-05-03",
        "description": "Danışmanlık tahsilatı",
        "amount": 7000.0,
        "direction": "inflow",
        "counterparty": "B Firması",
        "category": "Danışmanlık",
        "currency": "TRY",
        "source": "excel",
    },
    {
        "date": "2026-05-04",
        "description": "Personel ödemesi",
        "amount": 5000.0,
        "direction": "outflow",
        "category": "Personel",
        "currency": "TRY",
        "source": "excel",
    },
]


def main():
    os.environ.setdefault("REPORT_AI_ANALYSIS_ENABLED", "0")
    registry = ReportRegistryService()

    for report_id in ["income_expense_report", "cash_flow_report"]:
        report_definition = registry.get_report_definition(report_id)
        validation = validate_transactions(
            SAMPLE_TRANSACTIONS,
            report_definition=report_definition,
        )
        if not validation["valid"]:
            raise RuntimeError(validation["errors"])

        report_result = generate_report(
            report_definition=report_definition,
            report_input=validation["transactions"],
        )
        output = generate_outputs(
            report_definition=report_definition,
            intent={"filters": {}, "manual_sample": True},
            transactions=validation["transactions"],
            report_result=report_result,
            source_file=None,
            mapping=None,
            warnings=validation["warnings"],
        )
        print(f"{report_definition['display_name']}: {output['files']['xlsx']}")


if __name__ == "__main__":
    main()
