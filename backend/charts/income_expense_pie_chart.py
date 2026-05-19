from __future__ import annotations

import pandas as pd

from charts.base_chart_agent import BaseChartAgent


class IncomeExpensePieChartAgent(BaseChartAgent):
    artifact_id = "income_expense_pie_chart"
    display_name = "Gelir-Gider Pasta Grafiği"

    def build_figure(self, df: pd.DataFrame, user_prompt: str | None = None):
        self._require_rows(df)
        frame = df.copy()
        if "direction" in frame.columns and "amount" in frame.columns:
            income_total = float(frame.loc[frame["direction"] == "income", "amount"].fillna(0).sum())
            expense_total = float(frame.loc[frame["direction"] == "expense", "amount"].fillna(0).sum())
        else:
            income_total = float(frame.get("income", pd.Series(dtype=float)).fillna(0).sum())
            expense_total = float(frame.get("expense", pd.Series(dtype=float)).fillna(0).sum())
        if income_total <= 0 and expense_total <= 0:
            raise ValueError("Gelir veya gider toplami bulunamadigi icin pasta grafiği olusturulamadi.")

        fig, ax = self._figure("Gelir / Gider Dağılımı")
        values = [max(income_total, 0), max(expense_total, 0)]
        labels = [f"Gelir\n{income_total:,.0f} TL", f"Gider\n{expense_total:,.0f} TL"]
        ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90, colors=["#10b981", "#ef4444"], textprops={"fontsize": 12})
        ax.axis("equal")
        return fig
