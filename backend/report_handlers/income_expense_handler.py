from __future__ import annotations

import pandas as pd

from report_handlers.base_report_handler import BaseReportHandler


class IncomeExpenseReportHandler(BaseReportHandler):
    def compute(self, report_input: list[dict], intent: dict | None = None) -> dict:
        df = pd.DataFrame(report_input)
        income_total = total_by_direction(df, "income")
        expense_total = total_by_direction(df, "expense")
        net_profit = income_total - expense_total
        transaction_count = int(len(df))
        average_transaction_amount = safe_ratio(
            float(df["amount"].sum()) if not df.empty and "amount" in df else 0.0,
            transaction_count,
        )
        largest_income = largest_by_direction(df, "income")
        largest_expense = largest_by_direction(df, "expense")

        category_totals = category_totals_table(df)
        expense_breakdown = expense_category_breakdown(category_totals)
        daily_trend = daily_income_expense_trend(df)

        return {
            "summary": {
                "income_total": income_total,
                "expense_total": expense_total,
                "net_profit": net_profit,
                "profit_margin": safe_ratio(net_profit, income_total),
                "transaction_count": transaction_count,
                "average_transaction_amount": average_transaction_amount,
                "largest_income": largest_income,
                "largest_expense": largest_expense,
            },
            "tables": {
                "category_totals": category_totals,
                "daily_income_expense": daily_trend,
            },
            "charts": [
                {
                    "chart_id": "income_expense_comparison",
                    "type": "column",
                    "title": "Gelir Gider Karşılaştırması",
                    "data_source": "summary",
                    "priority": 1,
                    "labels": ["Toplam Gelir", "Toplam Gider", "Net Kar"],
                    "values": [income_total, expense_total, net_profit],
                    "value_type": "currency",
                },
                {
                    "chart_id": "expense_category_distribution",
                    "type": "pie",
                    "title": "Gider Kategorileri Dağılımı",
                    "data_source": "category_totals",
                    "priority": 2,
                    "labels": [row["category"] for row in expense_breakdown],
                    "values": [row["amount"] for row in expense_breakdown],
                    "value_type": "currency",
                },
                {
                    "chart_id": "daily_income_expense_trend",
                    "type": "line",
                    "title": "Günlük Gelir Gider Trendi",
                    "data_source": "daily_income_expense",
                    "priority": 3,
                    "labels": [row["date"] for row in daily_trend],
                    "series": [
                        {"name": "Gelir", "values": [row["income"] for row in daily_trend]},
                        {"name": "Gider", "values": [row["expense"] for row in daily_trend]},
                    ],
                    "value_type": "currency",
                },
                {
                    "chart_id": "cumulative_net_profit_trend",
                    "type": "line",
                    "title": "Kümülatif Net Kar Trendi",
                    "data_source": "daily_income_expense",
                    "priority": 4,
                    "labels": [row["date"] for row in daily_trend],
                    "values": [row["cumulative_net_profit"] for row in daily_trend],
                    "value_type": "currency",
                },
            ],
            "narrative": None,
            "warnings": [],
        }


def total_by_direction(df: pd.DataFrame, direction: str) -> float:
    if df.empty or "direction" not in df:
        return 0.0
    direction_values = equivalent_directions(direction)
    return float(df.loc[df["direction"].isin(direction_values), "amount"].sum())


def largest_by_direction(df: pd.DataFrame, direction: str) -> float:
    if df.empty or "direction" not in df or "amount" not in df:
        return 0.0
    direction_values = equivalent_directions(direction)
    values = df.loc[df["direction"].isin(direction_values), "amount"]
    if values.empty:
        return 0.0
    return float(values.max())


def category_totals_table(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    working_df = df.copy()
    if "category" not in working_df:
        working_df["category"] = "Diğer"
    working_df["category"] = working_df["category"].fillna("Diğer")

    rows = (
        working_df.groupby(["direction", "category"], dropna=False)["amount"]
        .sum()
        .reset_index()
        .to_dict(orient="records")
    )
    for row in rows:
        row["direction_label"] = "Gelir" if row["direction"] in equivalent_directions("income") else "Gider"
        row["amount"] = float(row.get("amount") or 0)
    return rows


def expense_category_breakdown(category_totals: list[dict]) -> list[dict]:
    return [
        row
        for row in category_totals
        if row.get("direction") in equivalent_directions("expense") and float(row.get("amount") or 0) > 0
    ]


def daily_income_expense_trend(df: pd.DataFrame) -> list[dict]:
    if df.empty or "date" not in df:
        return []

    working_df = df.copy()
    working_df["date"] = pd.to_datetime(working_df["date"], errors="coerce")
    working_df = working_df.dropna(subset=["date"])
    if working_df.empty:
        return []

    working_df["date_key"] = working_df["date"].dt.date
    working_df["income_amount"] = working_df.apply(
        lambda row: float(row["amount"]) if row["direction"] in equivalent_directions("income") else 0.0,
        axis=1,
    )
    working_df["expense_amount"] = working_df.apply(
        lambda row: float(row["amount"]) if row["direction"] in equivalent_directions("expense") else 0.0,
        axis=1,
    )

    daily = (
        working_df.groupby("date_key")[["income_amount", "expense_amount"]]
        .sum()
        .reset_index()
        .sort_values("date_key")
    )
    daily["net_profit"] = daily["income_amount"] - daily["expense_amount"]
    daily["cumulative_net_profit"] = daily["net_profit"].cumsum()

    return [
        {
            "date": str(row["date_key"]),
            "income": float(row["income_amount"]),
            "expense": float(row["expense_amount"]),
            "net_profit": float(row["net_profit"]),
            "cumulative_net_profit": float(row["cumulative_net_profit"]),
        }
        for _, row in daily.iterrows()
    ]


def safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return round(float(numerator / denominator), 4)


def equivalent_directions(direction: str) -> set[str]:
    if direction == "income":
        return {"income", "inflow"}
    if direction == "expense":
        return {"expense", "outflow"}
    return {direction}
