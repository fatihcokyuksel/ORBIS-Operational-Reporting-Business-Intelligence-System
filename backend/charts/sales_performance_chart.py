from __future__ import annotations

import pandas as pd

from charts.base_chart_agent import BaseChartAgent


class SalesPerformanceChartAgent(BaseChartAgent):
    artifact_id = "sales_performance_chart"
    display_name = "Satış Performans Grafiği"

    def build_figure(self, df: pd.DataFrame, user_prompt: str | None = None):
        self._require_rows(df)
        frame = df.copy()
        label_field = "product_name" if "product_name" in frame.columns else "customer"
        value_field = "total_sales" if "total_sales" in frame.columns else "amount"
        if label_field not in frame.columns or value_field not in frame.columns:
            raise ValueError("Satış performans grafiği için ürün/müşteri ve satış tutarı gereklidir.")
        grouped = frame.groupby(label_field, dropna=True)[value_field].sum().sort_values(ascending=False).head(10)
        self._require_rows(grouped.reset_index())
        fig, ax = self._figure("Satış Performansı")
        ax.bar(grouped.index.astype(str), grouped.values, color="#8b5cf6")
        ax.set_ylabel("Toplam Satış (TL)")
        ax.tick_params(axis="x", rotation=20)
        for idx, value in enumerate(grouped.values):
            ax.text(idx, value, f"{value:,.0f}", ha="center", va="bottom", fontsize=9)
        return fig
