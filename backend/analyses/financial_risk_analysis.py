from __future__ import annotations

import numpy as np
import pandas as pd

from analyses.base_analysis_agent import BaseAnalysisAgent


class FinancialRiskAnalysisAgent(BaseAnalysisAgent):
    artifact_id = "financial_risk_analysis"
    display_name = "Finansal Risk Analizi"

    def build_analysis(self, df: pd.DataFrame, user_prompt: str | None = None) -> dict:
        self._require_rows(df)
        frame = df.copy()
        income = float(frame.loc[frame["direction"] == "income", "amount"].fillna(0).sum())
        expense = float(frame.loc[frame["direction"] == "expense", "amount"].fillna(0).sum())
        net_cashflow = income - expense
        ratio = income / expense if expense else None
        daily = frame.copy()
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        if hasattr(daily["date"].dt, "tz") and daily["date"].dt.tz is not None:
            daily["date"] = daily["date"].dt.tz_localize(None)
        daily["signed_amount"] = daily["amount"].where(daily["direction"] == "income", -daily["amount"].abs())
        monthly_expense = daily.loc[daily["direction"] == "expense"].groupby(daily["date"].dt.to_period("M"))["amount"].sum()
        expense_trend = float(monthly_expense.diff().mean()) if len(monthly_expense) > 1 else 0.0
        volatility = float(daily.groupby(daily["date"].dt.date)["signed_amount"].sum().std(ddof=0) or 0.0)
        risk_score = min(100.0, max(0.0, 50 + (-net_cashflow / expense * 40 if expense else 0) + (volatility / expense * 100 if expense else 0)))
        metrics = {
            "toplam_gelir": round(income, 2),
            "toplam_gider": round(expense, 2),
            "net_nakit_akisi": round(net_cashflow, 2),
            "gelir_gider_orani": round(ratio, 4) if ratio is not None else None,
            "gider_trend_ortalamasi": round(expense_trend, 2),
            "nakit_oynakligi": round(volatility, 2),
            "risk_skoru": round(risk_score, 2),
        }
        narrative = self.generate_narrative({"artifact_id": self.artifact_id, "metrics": metrics, "user_prompt": user_prompt})
        return {
            "title": self.display_name,
            "summary": metrics,
            "narrative": narrative,
            "tables": [],
        }
