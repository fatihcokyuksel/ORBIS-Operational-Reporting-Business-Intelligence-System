from __future__ import annotations

import pandas as pd

from analyses.base_analysis_agent import BaseAnalysisAgent


class ReceivableDebtRiskAnalysisAgent(BaseAnalysisAgent):
    artifact_id = "receivable_debt_risk_analysis"
    display_name = "Borç-Alacak Risk Analizi"

    def build_analysis(self, df: pd.DataFrame, user_prompt: str | None = None) -> dict:
        self._require_rows(df)
        frame = df.copy()
        today = pd.Timestamp.today().normalize()
        if "due_date" in frame.columns:
            frame["due_date"] = pd.to_datetime(frame["due_date"], errors="coerce")
        overdue = frame[(frame.get("payment_status", "") != "paid") & frame["due_date"].notna() & (frame["due_date"] < today)] if "due_date" in frame.columns else frame.iloc[0:0]
        counterparty_field = "counterparty" if "counterparty" in frame.columns else "customer"
        grouped = frame.pivot_table(index=counterparty_field, columns="direction", values="amount", aggfunc="sum", fill_value=0)
        risky = grouped.assign(net_risk=grouped.get("receivable", 0) + grouped.get("debt", 0)).sort_values("net_risk", ascending=False).head(10)
        metrics = {
            "vadesi_gecmis_kayit": int(len(overdue)),
            "vadesi_gecmis_tutar": round(float(overdue["amount"].sum()), 2) if not overdue.empty else 0.0,
            "riskli_cari_sayisi": int(len(risky)),
        }
        rows = [[str(idx), f"{float(row.get('receivable', 0)):,.2f}", f"{float(row.get('debt', 0)):,.2f}", f"{float(row.get('net_risk', 0)):,.2f}"] for idx, row in risky.iterrows()]
        narrative = self.generate_narrative({"artifact_id": self.artifact_id, "metrics": metrics, "user_prompt": user_prompt})
        return {"title": self.display_name, "summary": metrics, "narrative": narrative, "tables": [{"title": "Riskli Cariler", "headers": ["Cari", "Alacak", "Borç", "Toplam Risk"], "rows": rows}]}
