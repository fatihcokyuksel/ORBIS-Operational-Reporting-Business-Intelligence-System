from __future__ import annotations

import pandas as pd

from charts.base_chart_agent import BaseChartAgent


class MonthlyExpenseTrendChartAgent(BaseChartAgent):
    artifact_id = "monthly_expense_trend_chart"
    display_name = "Aylık Harcama Trend Grafiği"

    def build_figure(self, df: pd.DataFrame, user_prompt: str | None = None):
        self._require_rows(df)
        frame = df.copy()
        if "direction" in frame.columns:
            frame = frame[frame["direction"] == "expense"].copy()
        self._require_rows(frame, "Gider trendi icin yeterli gider kaydi bulunamadi.")
        if "date" in frame.columns:
            frame["period"] = pd.to_datetime(frame["date"], errors="coerce").dt.to_period("M").astype(str)
            grouped = frame.groupby("period", dropna=True)["amount"].sum().reset_index()
        else:
            grouped = frame.groupby("period", dropna=True)["expense"].sum().reset_index()
            grouped = grouped.rename(columns={"expense": "amount"})
        self._require_rows(grouped)
        fig, ax = self._figure("Aylık Harcama Trendi")
        ax.plot(grouped["period"], grouped["amount"], marker="o", linewidth=2.5, color="#ef4444")
        ax.set_xlabel("Ay")
        ax.set_ylabel("Toplam Gider (TL)")
        ax.grid(alpha=0.2)
        for x, y in zip(grouped["period"], grouped["amount"]):
            ax.annotate(f"{y:,.0f}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", fontsize=10)
        return fig
