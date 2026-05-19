from __future__ import annotations

import pandas as pd

from charts.base_chart_agent import BaseChartAgent


class TaxDistributionChartAgent(BaseChartAgent):
    artifact_id = "tax_distribution_chart"
    display_name = "Vergi Dağılım Grafiği"

    def build_figure(self, df: pd.DataFrame, user_prompt: str | None = None):
        self._require_rows(df)
        frame = df.copy()
        label_field = "tax_type" if "tax_type" in frame.columns else "tax_rate"
        value_field = "tax_amount" if "tax_amount" in frame.columns else "amount"
        if label_field not in frame.columns or value_field not in frame.columns:
            raise ValueError("Vergi dağılım grafiği için vergi türü/oranı ve vergi tutarı gereklidir.")
        grouped = frame.groupby(label_field, dropna=True)[value_field].sum().sort_values(ascending=False)
        self._require_rows(grouped.reset_index())
        fig, ax = self._figure("Vergi Dağılımı")
        ax.pie(grouped.values, labels=grouped.index.astype(str), autopct="%1.1f%%", startangle=90)
        ax.axis("equal")
        return fig
