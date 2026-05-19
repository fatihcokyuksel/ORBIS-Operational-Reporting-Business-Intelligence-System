from __future__ import annotations

import pandas as pd

from charts.base_chart_agent import BaseChartAgent


class TopExpensesChartAgent(BaseChartAgent):
    artifact_id = "top_expenses_chart"
    display_name = "En Büyük Giderler Grafiği"

    def build_figure(self, df: pd.DataFrame, user_prompt: str | None = None):
        self._require_rows(df)
        frame = df.copy()
        if "direction" in frame.columns:
            frame = frame[frame["direction"] == "expense"].copy()
        label_field = "description" if "description" in frame.columns else "category"
        if label_field not in frame.columns or "amount" not in frame.columns:
            raise ValueError("En büyük giderler grafiği için açıklama/kategori ve tutar alanları gereklidir.")
        grouped = frame.groupby(label_field, dropna=True)["amount"].sum().sort_values(ascending=False).head(10).sort_values()
        self._require_rows(grouped.reset_index(), "Gosterilecek gider verisi bulunamadi.")
        fig, ax = self._figure("En Büyük 10 Gider")
        ax.barh(grouped.index.astype(str), grouped.values, color="#f97316")
        ax.set_xlabel("Toplam Gider (TL)")
        for idx, value in enumerate(grouped.values):
            ax.text(value, idx, f" {value:,.0f}", va="center", fontsize=10)
        return fig
