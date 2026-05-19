from __future__ import annotations

from datetime import timedelta

import pandas as pd

from analyses.base_analysis_agent import BaseAnalysisAgent


class CashRunwayAnalysisAgent(BaseAnalysisAgent):
    artifact_id = "cash_runway_analysis"
    display_name = "Nakit Tükenme Riski Analizi"

    def build_analysis(self, df: pd.DataFrame, user_prompt: str | None = None) -> dict:
        self._require_rows(df)
        frame = df.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        expenses = frame.loc[frame["direction"] == "expense"].copy()
        incomes = frame.loc[frame["direction"] == "income"].copy()
        avg_daily_burn = float(expenses.groupby(expenses["date"].dt.date)["amount"].sum().mean() or 0.0)
        avg_monthly_expense = float(expenses.groupby(expenses["date"].dt.to_period("M"))["amount"].sum().mean() or 0.0)
        if "balance" in frame.columns and frame["balance"].notna().any():
            current_balance = float(frame["balance"].dropna().iloc[-1])
        else:
            current_balance = float(incomes["amount"].sum() - expenses["amount"].sum())
        runway_days = float(current_balance / avg_daily_burn) if avg_daily_burn > 0 else None
        latest_date = frame["date"].dropna().max()
        critical_date = (latest_date + timedelta(days=int(runway_days))) if latest_date is not None and runway_days else None
        metrics = {
            "mevcut_bakiye": round(current_balance, 2),
            "ortalama_gunluk_yakim": round(avg_daily_burn, 2),
            "ortalama_aylik_gider": round(avg_monthly_expense, 2),
            "nakit_runway_gun": round(runway_days, 1) if runway_days is not None else None,
            "kritik_tarih": critical_date.date().isoformat() if critical_date is not None else None,
        }
        narrative = self.generate_narrative({"artifact_id": self.artifact_id, "metrics": metrics, "user_prompt": user_prompt})
        return {"title": self.display_name, "summary": metrics, "narrative": narrative, "tables": []}
