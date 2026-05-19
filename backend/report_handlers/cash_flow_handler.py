from __future__ import annotations

import pandas as pd

from report_handlers.base_report_handler import BaseReportHandler


class CashFlowReportHandler(BaseReportHandler):
    def check_applicability(self, normalized_payload: list[dict], intent: dict | None = None) -> dict:
        if any(not item.get("date") for item in normalized_payload):
            return {
                "status": "failed",
                "warnings": [],
                "message": "Nakit akış raporu için tüm kayıtlarda tarih alanı gereklidir.",
            }
        return super().check_applicability(normalized_payload, intent)

    def compute(self, report_input: list[dict], intent: dict | None = None) -> dict:
        df = pd.DataFrame(report_input)
        working_df = df.copy()
        working_df["date"] = pd.to_datetime(working_df["date"], errors="coerce")
        working_df = working_df.dropna(subset=["date"])
        working_df["signed_amount"] = working_df.apply(
            lambda row: row["amount"] if row["direction"] in equivalent_directions("income") else -row["amount"],
            axis=1,
        )

        daily = build_daily_cash_flow(working_df)
        outflow_categories = outflow_category_breakdown(working_df)
        activity_cash_flow = activity_cash_flow_summary(working_df)

        income_total = total_by_direction(working_df, "income")
        expense_total = total_by_direction(working_df, "expense")
        net_cash_flow = income_total - expense_total
        transaction_count = int(len(df))

        return {
            "summary": {
                "cash_in_total": income_total,
                "cash_out_total": expense_total,
                "net_cash_flow": net_cash_flow,
                "transaction_count": transaction_count,
                "average_transaction_amount": safe_ratio(
                    float(df["amount"].sum()) if not df.empty and "amount" in df else 0.0,
                    transaction_count,
                ),
                "largest_cash_in": largest_by_direction(working_df, "income"),
                "largest_cash_out": largest_by_direction(working_df, "expense"),
                "ending_balance": ending_balance(daily),
                "average_daily_cash_in": average_daily_value(daily, "cash_in"),
                "average_daily_cash_out": average_daily_value(daily, "cash_out"),
                "positive_cash_flow_day_count": day_count_by_sign(daily, positive=True),
                "negative_cash_flow_day_count": day_count_by_sign(daily, positive=False),
                "operating_cash_flow": activity_cash_flow["operating"],
                "investing_cash_flow": activity_cash_flow["investing"],
                "financing_cash_flow": activity_cash_flow["financing"],
                "unclassified_cash_flow": activity_cash_flow["unclassified"],
            },
            "tables": {
                "daily_cash_flow": daily,
                "outflow_category_totals": outflow_categories,
                "activity_cash_flow": [
                    {"activity": key, "amount": value}
                    for key, value in activity_cash_flow.items()
                ],
            },
            "charts": [
                {
                    "chart_id": "cash_in_out_comparison",
                    "type": "column",
                    "title": "Nakit Girişi Çıkışı Karşılaştırması",
                    "data_source": "summary",
                    "priority": 1,
                    "labels": ["Nakit Girişi", "Nakit Çıkışı", "Net Nakit Akışı"],
                    "values": [income_total, expense_total, net_cash_flow],
                    "value_type": "currency",
                },
                {
                    "chart_id": "cumulative_balance_trend",
                    "type": "line",
                    "title": "Kümülatif Bakiye Trendi",
                    "data_source": "daily_cash_flow",
                    "priority": 2,
                    "labels": [row["date"] for row in daily],
                    "values": [row["balance_or_cumulative_cash"] for row in daily],
                    "value_type": "currency",
                },
                {
                    "chart_id": "cash_out_category_distribution",
                    "type": "pie",
                    "title": "Nakit Çıkış Kategorileri",
                    "data_source": "outflow_category_totals",
                    "priority": 3,
                    "labels": [row["category"] for row in outflow_categories],
                    "values": [row["amount"] for row in outflow_categories],
                    "value_type": "currency",
                },
                {
                    "chart_id": "daily_net_cash_flow_trend",
                    "type": "line",
                    "title": "Günlük Net Nakit Akışı Trendi",
                    "data_source": "daily_cash_flow",
                    "priority": 4,
                    "labels": [row["date"] for row in daily],
                    "values": [row["net_cash_flow"] for row in daily],
                    "value_type": "currency",
                },
            ],
            "narrative": None,
            "warnings": [],
        }


def build_daily_cash_flow(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []

    working_df = df.copy()
    working_df["date_key"] = working_df["date"].dt.date
    working_df["cash_in"] = working_df.apply(
        lambda row: float(row["amount"]) if row["direction"] in equivalent_directions("income") else 0.0,
        axis=1,
    )
    working_df["cash_out"] = working_df.apply(
        lambda row: float(row["amount"]) if row["direction"] in equivalent_directions("expense") else 0.0,
        axis=1,
    )

    daily = (
        working_df.groupby("date_key")[["cash_in", "cash_out", "signed_amount"]]
        .sum()
        .reset_index()
        .sort_values("date_key")
        .rename(columns={"signed_amount": "net_cash_flow"})
    )
    daily["cumulative_cash_flow"] = daily["net_cash_flow"].cumsum()

    balance_by_date = daily_balance_by_date(working_df)
    rows = []
    for _, row in daily.iterrows():
        date_key = row["date_key"]
        balance = balance_by_date.get(date_key)
        cumulative_cash = float(row["cumulative_cash_flow"])
        rows.append(
            {
                "date": str(date_key),
                "cash_in": float(row["cash_in"]),
                "cash_out": float(row["cash_out"]),
                "net_cash_flow": float(row["net_cash_flow"]),
                "cumulative_cash_flow": cumulative_cash,
                "balance": balance,
                "balance_or_cumulative_cash": balance if balance is not None else cumulative_cash,
            }
        )
    return rows


def daily_balance_by_date(df: pd.DataFrame) -> dict:
    if "balance" not in df:
        return {}
    balance_df = df.dropna(subset=["balance"]).copy()
    if balance_df.empty:
        return {}
    balance_df = balance_df.sort_values("date")
    return {
        row["date"].date(): float(row["balance"])
        for _, row in balance_df.groupby(balance_df["date"].dt.date).tail(1).iterrows()
    }


def outflow_category_breakdown(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    working_df = df[df["direction"].isin(equivalent_directions("expense"))].copy()
    if working_df.empty:
        return []
    if "category" not in working_df:
        working_df["category"] = "Diğer"
    working_df["category"] = working_df["category"].fillna("Diğer")
    rows = (
        working_df.groupby("category", dropna=False)["amount"]
        .sum()
        .reset_index()
        .to_dict(orient="records")
    )
    return [
        {"category": row["category"], "amount": float(row.get("amount") or 0)}
        for row in rows
        if float(row.get("amount") or 0) > 0
    ]


def activity_cash_flow_summary(df: pd.DataFrame) -> dict:
    summary = {
        "operating": 0.0,
        "investing": 0.0,
        "financing": 0.0,
        "unclassified": 0.0,
    }
    if df.empty:
        return summary

    for _, row in df.iterrows():
        activity = classify_activity(row.get("category"))
        summary[activity] += float(row.get("signed_amount") or 0)
    return {key: round(value, 2) for key, value in summary.items()}


def classify_activity(category) -> str:
    if category is None or pd.isna(category) or not str(category).strip():
        return "unclassified"

    text = normalize_category_text(category)
    operating_keywords = [
        "operating",
        "operasyon",
        "satis",
        "musteri",
        "maas",
        "kira",
        "vergi",
        "tedarikci",
        "hizmet",
        "personel",
    ]
    investing_keywords = [
        "investment",
        "yatirim",
        "duran varlik",
        "ekipman",
        "sunucu",
        "lisans",
        "varlik alimi",
    ]
    financing_keywords = [
        "financing",
        "finansman",
        "kredi",
        "sermaye",
        "yatirimci",
        "faiz",
        "borc",
    ]

    if any(keyword in text for keyword in operating_keywords):
        return "operating"
    if any(keyword in text for keyword in investing_keywords):
        return "investing"
    if any(keyword in text for keyword in financing_keywords):
        return "financing"
    return "unclassified"


def normalize_category_text(value) -> str:
    text = str(value).strip().lower()
    replacements = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def ending_balance(daily: list[dict]) -> float | None:
    if not daily:
        return None

    for row in reversed(daily):
        if row.get("balance") is not None:
            return float(row["balance"])

    latest = daily[-1].get("balance_or_cumulative_cash")
    return float(latest) if latest is not None else None


def average_daily_value(daily: list[dict], key: str) -> float | None:
    if not daily:
        return None
    return round(sum(float(row.get(key) or 0) for row in daily) / len(daily), 2)


def day_count_by_sign(daily: list[dict], positive: bool) -> int:
    if positive:
        return sum(1 for row in daily if float(row.get("net_cash_flow") or 0) > 0)
    return sum(1 for row in daily if float(row.get("net_cash_flow") or 0) < 0)


def total_by_direction(df: pd.DataFrame, direction: str) -> float:
    if df.empty or "direction" not in df:
        return 0.0
    return float(df.loc[df["direction"].isin(equivalent_directions(direction)), "amount"].sum())


def largest_by_direction(df: pd.DataFrame, direction: str) -> float:
    if df.empty or "direction" not in df or "amount" not in df:
        return 0.0
    values = df.loc[df["direction"].isin(equivalent_directions(direction)), "amount"]
    if values.empty:
        return 0.0
    return float(values.max())


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
