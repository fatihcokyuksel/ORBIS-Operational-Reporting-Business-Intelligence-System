from __future__ import annotations

import pandas as pd

from charts.base_chart_agent import BaseChartAgent


class DailyBalanceChangeChartAgent(BaseChartAgent):
    artifact_id = "daily_balance_change_chart"
    display_name = "Günlük Bakiye Değişim Grafiği"

    def build_figure(self, df: pd.DataFrame, user_prompt: str | None = None):
        self._require_rows(df)
        frame = df.copy()
        if "date" not in frame.columns:
            raise ValueError("Bakiye değişim grafiği için tarih alanı gereklidir.")
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        if "balance" in frame.columns:
            daily = frame.sort_values("date")[["date", "balance"]].dropna()
        elif "amount" in frame.columns and "direction" in frame.columns:
            frame["signed_amount"] = frame["amount"].where(frame["direction"] == "income", -frame["amount"].abs())
            daily = frame.sort_values("date").groupby(frame["date"].dt.date)["signed_amount"].sum().cumsum().reset_index()
            daily.columns = ["date", "balance"]
        else:
            raise ValueError("Bakiye veya yönlü işlem tutarı olmadan bakiye değişim grafiği üretilemedi.")
        self._require_rows(daily)
        fig, ax = self._figure("Günlük Bakiye Değişimi")
        ax.plot(daily["date"], daily["balance"], color="#2563eb", linewidth=2.5)
        ax.set_xlabel("Tarih")
        ax.set_ylabel("Bakiye (TL)")
        ax.grid(alpha=0.2)
        return fig
