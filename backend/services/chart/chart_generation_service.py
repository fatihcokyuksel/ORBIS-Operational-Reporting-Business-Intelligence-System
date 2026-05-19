from __future__ import annotations

from pathlib import Path

import pandas as pd

from charts.balance_change_chart import DailyBalanceChangeChartAgent
from charts.cashflow_bar_chart import CashflowBarChartAgent
from charts.income_expense_pie_chart import IncomeExpensePieChartAgent
from charts.monthly_expense_trend_chart import MonthlyExpenseTrendChartAgent
from charts.receivable_debt_distribution_chart import DebtReceivableDistributionChartAgent
from charts.sales_performance_chart import SalesPerformanceChartAgent
from charts.tax_distribution_chart import TaxDistributionChartAgent
from charts.top_expenses_chart import TopExpensesChartAgent
from utils.chart_writer import save_chart_figure


CHART_AGENTS = {
    "income_expense_pie_chart": IncomeExpensePieChartAgent,
    "monthly_expense_trend_chart": MonthlyExpenseTrendChartAgent,
    "cashflow_bar_chart": CashflowBarChartAgent,
    "top_expenses_chart": TopExpensesChartAgent,
    "daily_balance_change_chart": DailyBalanceChangeChartAgent,
    "debt_receivable_distribution_chart": DebtReceivableDistributionChartAgent,
    "sales_performance_chart": SalesPerformanceChartAgent,
    "tax_distribution_chart": TaxDistributionChartAgent,
}


def generate_chart_artifact(artifact_id: str, df: pd.DataFrame, output_dir: str | Path, user_prompt: str | None = None) -> dict:
    agent_class = CHART_AGENTS.get(artifact_id)
    if agent_class is None:
        raise ValueError(f"Desteklenmeyen grafik tipi: {artifact_id}")
    agent = agent_class()
    fig = agent.build_figure(df, user_prompt=user_prompt)
    output_path = save_chart_figure(fig, output_dir, file_name="chart.jpg")
    return {"output_file_path": output_path, "output_file_name": "chart.jpg", "summary": {"row_count": int(len(df))}}
