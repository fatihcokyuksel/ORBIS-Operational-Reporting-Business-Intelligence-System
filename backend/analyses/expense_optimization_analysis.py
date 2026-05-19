from __future__ import annotations

import pandas as pd

from analyses.base_analysis_agent import BaseAnalysisAgent


class ExpenseOptimizationAnalysisAgent(BaseAnalysisAgent):
    artifact_id = "expense_optimization_analysis"
    display_name = "Gider Optimizasyon Analizi"

    def build_analysis(self, df: pd.DataFrame, user_prompt: str | None = None) -> dict:
        frame = df.loc[df["direction"] == "expense"].copy() if "direction" in df.columns else df.copy()
        self._require_rows(frame)
        category_field = "category" if "category" in frame.columns else "description"
        category_totals = frame.groupby(category_field)["amount"].sum().sort_values(ascending=False)
        recurring = frame.groupby("description")["amount"].agg(["count", "sum"]).sort_values(["count", "sum"], ascending=False) if "description" in frame.columns else pd.DataFrame()
        potential_savings = float(category_totals.head(3).sum() * 0.1) if not category_totals.empty else 0.0
        metrics = {
            "toplam_gider": round(float(frame["amount"].sum()), 2),
            "en_buyuk_kategori_pay": round(float(category_totals.iloc[0] / frame["amount"].sum() * 100), 2) if not category_totals.empty else 0.0,
            "ilk_uc_kategori_payi": round(float(category_totals.head(3).sum() / frame["amount"].sum() * 100), 2) if not category_totals.empty else 0.0,
            "potansiyel_tasarruf": round(potential_savings, 2),
        }
        rows = [[str(idx), f"{float(val):,.2f}"] for idx, val in category_totals.head(10).items()]
        recurring_rows = [[str(idx), int(row["count"]), f"{float(row['sum']):,.2f}"] for idx, row in recurring.head(10).iterrows()] if not recurring.empty else []
        narrative = self.generate_narrative({"artifact_id": self.artifact_id, "metrics": metrics, "user_prompt": user_prompt})
        return {
            "title": self.display_name,
            "summary": metrics,
            "narrative": narrative,
            "tables": [
                {"title": "Kategori Bazlı Giderler", "headers": ["Kategori", "Toplam Tutar"], "rows": rows},
                {"title": "Tekrarlayan Giderler", "headers": ["Açıklama", "Tekrar", "Toplam"], "rows": recurring_rows},
            ],
        }
