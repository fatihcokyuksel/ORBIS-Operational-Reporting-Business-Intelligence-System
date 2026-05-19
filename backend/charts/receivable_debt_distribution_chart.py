from __future__ import annotations

import pandas as pd

from charts.base_chart_agent import BaseChartAgent


class DebtReceivableDistributionChartAgent(BaseChartAgent):
    artifact_id = "debt_receivable_distribution_chart"
    display_name = "Borç-Alacak Dağılım Grafiği"

    def build_figure(self, df: pd.DataFrame, user_prompt: str | None = None):
        self._require_rows(df)
        frame = df.copy()
        name_field = "counterparty" if "counterparty" in frame.columns else "customer"
        if name_field not in frame.columns:
            raise ValueError("Borç-alacak dağılımı için cari alanı bulunamadi.")
        if "direction" in frame.columns and "amount" in frame.columns:
            grouped = frame.pivot_table(index=name_field, columns="direction", values="amount", aggfunc="sum", fill_value=0)
        else:
            grouped = frame.groupby(name_field)[["debt_amount", "receivable_amount"]].sum()
            grouped = grouped.rename(columns={"debt_amount": "debt", "receivable_amount": "receivable"})
        grouped = grouped.sort_values(by=list(grouped.columns), ascending=False).head(10)
        self._require_rows(grouped.reset_index())
        fig, ax = self._figure("Cari Bazlı Borç / Alacak Dağılımı")
        x = range(len(grouped))
        ax.bar([i - 0.18 for i in x], grouped.get("receivable", 0), width=0.35, label="Alacak", color="#10b981")
        ax.bar([i + 0.18 for i in x], grouped.get("debt", 0), width=0.35, label="Borç", color="#ef4444")
        ax.set_xticks(list(x), grouped.index.astype(str), rotation=20, ha="right")
        ax.set_ylabel("Tutar (TL)")
        ax.legend()
        return fig
