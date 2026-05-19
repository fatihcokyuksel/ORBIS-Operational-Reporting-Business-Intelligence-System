from __future__ import annotations

from collections import defaultdict

import pandas as pd

from report_handlers.base_report_handler import BaseReportHandler


class DebtReceivableReportHandler(BaseReportHandler):
    def compute(self, report_input: list[dict], intent: dict | None = None) -> dict:
        df = pd.DataFrame(report_input)
        debt_total = total_by_direction(df, "debt")
        receivable_total = total_by_direction(df, "receivable")
        net_position = receivable_total - debt_total

        category_totals = defaultdict(float)
        for _, row in df.iterrows():
            key = f"{row['direction']}::{row.get('category') or 'Diger'}"
            category_totals[key] += float(row["amount"])

        return {
            "summary": {
                "debt_total": debt_total,
                "receivable_total": receivable_total,
                "net_position": net_position,
                "transaction_count": int(len(df)),
            },
            "tables": {
                "category_totals": [
                    {"bucket": key, "amount": value}
                    for key, value in sorted(category_totals.items())
                ],
            },
            "charts": [
                {
                    "chart_id": "debt_receivable_overview",
                    "type": "bar",
                    "labels": ["Borc", "Alacak"],
                    "values": [debt_total, receivable_total],
                }
            ],
            "narrative": None,
            "warnings": [],
        }


def total_by_direction(df: pd.DataFrame, direction: str) -> float:
    if df.empty or "direction" not in df:
        return 0.0
    return float(df.loc[df["direction"] == direction, "amount"].sum())
