from __future__ import annotations

import pandas as pd

from analyses.base_analysis_agent import BaseAnalysisAgent


class TaxRiskAnalysisAgent(BaseAnalysisAgent):
    artifact_id = "tax_risk_analysis"
    display_name = "Vergi Risk Analizi"

    def build_analysis(self, df: pd.DataFrame, user_prompt: str | None = None) -> dict:
        self._require_rows(df)
        frame = df.copy()
        tax_amount_field = "tax_amount" if "tax_amount" in frame.columns else "amount"
        distribution = frame.groupby("tax_type")[tax_amount_field].sum().sort_values(ascending=False) if "tax_type" in frame.columns else pd.Series(dtype=float)
        inconsistencies = pd.Series(dtype=float)
        if {"tax_rate", "base_amount", tax_amount_field}.issubset(frame.columns):
            expected = frame["base_amount"].fillna(0) * frame["tax_rate"].fillna(0)
            diff = (expected - frame[tax_amount_field].fillna(0)).abs()
            inconsistencies = frame.loc[diff > 1.0, tax_amount_field]
        metrics = {
            "toplam_vergi_tutari": round(float(frame[tax_amount_field].sum()), 2),
            "vergi_turu_sayisi": int(frame["tax_type"].nunique()) if "tax_type" in frame.columns else 0,
            "tutarsiz_kayit_sayisi": int(len(inconsistencies)),
        }
        rows = [[str(idx), f"{float(val):,.2f}"] for idx, val in distribution.items()]
        narrative = self.generate_narrative({"artifact_id": self.artifact_id, "metrics": metrics, "user_prompt": user_prompt})
        return {"title": self.display_name, "summary": metrics, "narrative": narrative, "tables": [{"title": "Vergi Dağılımı", "headers": ["Vergi Türü", "Tutar"], "rows": rows}]}
