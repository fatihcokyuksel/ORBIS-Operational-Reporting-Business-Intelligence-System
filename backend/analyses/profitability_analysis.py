from __future__ import annotations

import pandas as pd

from analyses.base_analysis_agent import BaseAnalysisAgent


class ProfitabilityAnalysisAgent(BaseAnalysisAgent):
    artifact_id = "profitability_analysis"
    display_name = "Kârlılık Analizi"

    def build_analysis(self, df: pd.DataFrame, user_prompt: str | None = None) -> dict:
        self._require_rows(df)
        frame = df.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        income = float(frame.loc[frame["direction"] == "income", "amount"].sum())
        expense = float(frame.loc[frame["direction"] == "expense", "amount"].sum())
        monthly = frame.pivot_table(index=frame["date"].dt.to_period("M"), columns="direction", values="amount", aggfunc="sum", fill_value=0)
        monthly["net_profit"] = monthly.get("income", 0) - monthly.get("expense", 0)
        metrics = {
            "net_kar_zarar": round(income - expense, 2),
            "kar_marji": round(((income - expense) / income) * 100, 2) if income else None,
            "gider_gelir_orani": round((expense / income) * 100, 2) if income else None,
            "negatif_ay_sayisi": int((monthly["net_profit"] < 0).sum()) if not monthly.empty else 0,
        }
        rows = [[str(idx), f"{float(row.get('income', 0)):,.2f}", f"{float(row.get('expense', 0)):,.2f}", f"{float(row.get('net_profit', 0)):,.2f}"] for idx, row in monthly.reset_index().set_index("date").iterrows()]
        narrative = self.generate_narrative({"artifact_id": self.artifact_id, "metrics": metrics, "user_prompt": user_prompt})
        return {"title": self.display_name, "summary": metrics, "narrative": narrative, "tables": [{"title": "Aylık Kârlılık", "headers": ["Dönem", "Gelir", "Gider", "Net"], "rows": rows}]}
