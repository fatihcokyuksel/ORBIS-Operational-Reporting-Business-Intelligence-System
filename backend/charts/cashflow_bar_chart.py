from __future__ import annotations

import pandas as pd

from charts.base_chart_agent import BaseChartAgent


class CashflowBarChartAgent(BaseChartAgent):
    artifact_id = "cashflow_bar_chart"
    display_name = "Nakit Akış Bar Grafiği"

    def build_figure(self, df: pd.DataFrame, user_prompt: str | None = None):
        self._require_rows(df)
        frame = df.copy()
        if "date" not in frame.columns or "amount" not in frame.columns or "direction" not in frame.columns:
            raise ValueError("Nakit akış grafiği için tarih, tutar ve yön alanları gereklidir.")
        frame["period"] = pd.to_datetime(frame["date"], errors="coerce").dt.to_period("M").astype(str)
        grouped = frame.pivot_table(index="period", columns="direction", values="amount", aggfunc="sum", fill_value=0).reset_index()
        self._require_rows(grouped)
        grouped["net"] = grouped.get("income", 0) - grouped.get("expense", 0)
        fig, ax = self._figure("Aylık Nakit Akışı")
        x = range(len(grouped))
        ax.bar([i - 0.18 for i in x], grouped.get("income", 0), width=0.35, label="Gelir", color="#10b981")
        ax.bar([i + 0.18 for i in x], grouped.get("expense", 0), width=0.35, label="Gider", color="#ef4444")
        ax.plot(list(x), grouped["net"], color="#1d4ed8", marker="o", linewidth=2, label="Net Nakit Akışı")
        ax.set_xticks(list(x), grouped["period"])
        ax.set_xlabel("Ay")
        ax.set_ylabel("Tutar (TL)")
        ax.legend()
        ax.grid(axis="y", alpha=0.2)
        return fig
