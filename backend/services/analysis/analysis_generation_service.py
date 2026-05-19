from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from analyses.anomaly_spending_analysis import AnomalySpendingAnalysisAgent
from analyses.cash_runway_analysis import CashRunwayAnalysisAgent
from analyses.expense_optimization_analysis import ExpenseOptimizationAnalysisAgent
from analyses.financial_risk_analysis import FinancialRiskAnalysisAgent
from analyses.profitability_analysis import ProfitabilityAnalysisAgent
from analyses.receivable_debt_risk_analysis import ReceivableDebtRiskAnalysisAgent
from analyses.sales_risk_analysis import SalesRiskAnalysisAgent
from analyses.tax_risk_analysis import TaxRiskAnalysisAgent
from utils.pdf_writer import build_analysis_pdf
from services.localization_service import prettify_label


ANALYSIS_AGENTS = {
    "financial_risk_analysis": FinancialRiskAnalysisAgent,
    "cash_runway_analysis": CashRunwayAnalysisAgent,
    "anomaly_spending_analysis": AnomalySpendingAnalysisAgent,
    "expense_optimization_analysis": ExpenseOptimizationAnalysisAgent,
    "profitability_analysis": ProfitabilityAnalysisAgent,
    "receivable_debt_risk_analysis": ReceivableDebtRiskAnalysisAgent,
    "sales_risk_analysis": SalesRiskAnalysisAgent,
    "tax_risk_analysis": TaxRiskAnalysisAgent,
}

PAGE_TITLES = {
    "financial_risk_analysis": [
        "Kapak ve Yonetici Ozeti",
        "Veri Kapsami ve Kalite Ozeti",
        "Temel Finansal Metrikler",
        "Trend ve Donemsel Degisim Analizi",
        "Risk Faktorleri",
        "Oneriler ve Aksiyon Plani",
        "Metodoloji ve Limitasyonlar",
    ],
    "cash_runway_analysis": [
        "Yonetici Ozeti",
        "Nakit Giris-Cikis Profili",
        "Burn Rate Analizi",
        "Senaryo Analizi",
        "Riskler",
        "Oneriler",
        "Metodoloji",
    ],
    "anomaly_spending_analysis": [
        "Yonetici Ozeti",
        "Veri Kapsami",
        "Anomali Tespit Metodolojisi",
        "En Kritik Anormal Islemler",
        "Kategori Bazli Anomali Analizi",
        "Risk Yorumu",
        "Oneriler",
    ],
    "expense_optimization_analysis": [
        "Yonetici Ozeti",
        "Gider Dagilimi",
        "Trend Analizi",
        "Tekrarlayan Giderler",
        "Tasarruf Potansiyeli",
        "Aksiyon Plani",
        "Metodoloji",
    ],
    "profitability_analysis": [
        "Yonetici Ozeti",
        "Gelir Analizi",
        "Gider Analizi",
        "Aylik Karlilik",
        "Karlilik Riskleri",
        "Oneriler",
        "Metodoloji",
    ],
    "receivable_debt_risk_analysis": [
        "Yonetici Ozeti",
        "Cari Dagilimi",
        "Vade Analizi",
        "Riskli Cariler",
        "Tahsilat ve Odeme Riski",
        "Oneriler",
        "Metodoloji",
    ],
    "sales_risk_analysis": [
        "Yonetici Ozeti",
        "Satis Trend Analizi",
        "Urun Performansi",
        "Musteri Performansi",
        "Bolge ve Temsilci Analizi",
        "Riskler",
        "Oneriler ve Metodoloji",
    ],
    "tax_risk_analysis": [
        "Yonetici Ozeti",
        "Vergi Turu Dagilimi",
        "KDV Riskleri",
        "Aykiri Vergi Kayitlari",
        "Donemsel Vergi Trendleri",
        "Kontrol Onerileri",
        "Metodoloji ve Limitasyonlar",
    ],
}

TABLE_SLOTS = {
    "anomaly_spending_analysis": {4: 0},
    "expense_optimization_analysis": {2: 0, 4: 1},
    "profitability_analysis": {4: 0},
    "receivable_debt_risk_analysis": {4: 0},
    "sales_risk_analysis": {4: 0},
    "tax_risk_analysis": {2: 0},
}


def generate_analysis_artifact(
    artifact_id: str,
    df: pd.DataFrame,
    output_dir: str | Path,
    user_prompt: str | None = None,
    source_files: list[str] | None = None,
    warnings: list[dict] | None = None,
    filter_summary: dict | None = None,
) -> dict:
    agent_class = ANALYSIS_AGENTS.get(artifact_id)
    if agent_class is None:
        raise ValueError(f"Desteklenmeyen analiz tipi: {artifact_id}")

    agent = agent_class()
    analysis_payload = agent.build_analysis(df, user_prompt=user_prompt)
    package = build_analysis_package(
        artifact_id=artifact_id,
        title=analysis_payload.get("title", artifact_id),
        df=df,
        analysis_payload=analysis_payload,
        user_prompt=user_prompt,
        source_files=source_files or [],
        warnings=warnings or [],
        filter_summary=filter_summary or {},
    )
    output_path = Path(output_dir) / "analysis.pdf"
    build_analysis_pdf(
        output_path=output_path,
        title=package["title"],
        artifact_id=artifact_id,
        pages=package["pages"],
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        audit_run_id=Path(output_dir).name,
    )
    return {
        "output_file_path": str(output_path),
        "output_file_name": "analysis.pdf",
        "summary": analysis_payload.get("summary", {}),
    }


def build_analysis_package(
    artifact_id: str,
    title: str,
    df: pd.DataFrame,
    analysis_payload: dict,
    user_prompt: str | None,
    source_files: list[str],
    warnings: list[dict],
    filter_summary: dict,
) -> dict:
    narrative = analysis_payload.get("narrative", {})
    summary = analysis_payload.get("summary", {})
    data_scope = build_data_scope(df, source_files, warnings, filter_summary)
    figures = build_analysis_figures(artifact_id, df)
    tables = analysis_payload.get("tables", []) or []
    page_titles = PAGE_TITLES[artifact_id]

    pages = [
        {
            "title": page_titles[0],
            "subtitle": f"{title} | {describe_period(df)} | Kayit sayisi: {len(df)}",
            "blocks": [
                {"type": "metrics", "items": build_metric_items(summary, limit=4)},
                {"type": "paragraph", "text": narrative.get("executive_summary", "")},
                {"type": "table", "title": "En Onemli 3 Risk", "headers": ["Risk", "Aciklama"], "rows": [[f"Risk {idx}", text] for idx, text in enumerate(extract_key_points(narrative.get("risk_analysis", ""))[:3], start=1)]},
            ],
        },
        {
            "title": page_titles[1],
            "blocks": [
                {"type": "kv_table", "items": list(data_scope.items())},
                {"type": "paragraph", "text": narrative.get("data_scope_commentary", "")},
                {"type": "callout", "text": build_data_quality_callout(warnings, filter_summary, user_prompt)},
            ],
        },
        {
            "title": page_titles[2],
            "blocks": [
                {"type": "table", "title": "Temel Metrikler", "headers": ["Metrik", "Deger"], "rows": [[item["label"], item["value"]] for item in build_metric_items(summary, limit=12)]},
                {"type": "paragraph", "text": narrative.get("metric_commentary", "")},
            ],
        },
        {
            "title": page_titles[3],
            "blocks": build_page_four_blocks(artifact_id, figures, tables, narrative),
        },
        {
            "title": page_titles[4],
            "blocks": build_page_five_blocks(artifact_id, figures, tables, narrative, df),
        },
        {
            "title": page_titles[5],
            "blocks": [
                {"type": "paragraph", "text": narrative.get("findings", "")},
                {"type": "paragraph", "text": narrative.get("recommendations", "")},
            ],
        },
        {
            "title": page_titles[6],
            "blocks": [
                {"type": "paragraph", "text": narrative.get("methodology_explanation", "")},
                {"type": "paragraph", "text": narrative.get("limitations", "")},
                {"type": "kv_table", "items": build_methodology_items(df, filter_summary, warnings)},
                {"type": "callout", "text": "Bu rapor yonetsel on analiz amaciyla uretilmistir; muhasebesel kesin rapor yerine gecmez."},
            ],
        },
    ]

    return {
        "title": title,
        "cover_metrics": build_metric_items(summary, limit=4),
        "data_scope": data_scope,
        "metric_tables": tables,
        "chart_specs": figures,
        "risk_blocks": extract_key_points(narrative.get("risk_analysis", "")),
        "recommendation_blocks": extract_key_points(narrative.get("recommendations", "")),
        "methodology_blocks": extract_key_points(narrative.get("methodology_explanation", "")),
        "limitations": narrative.get("limitations", ""),
        "pages": pages,
    }


def build_page_four_blocks(artifact_id: str, figures: list, tables: list[dict], narrative: dict) -> list[dict]:
    blocks = []
    if figures:
        blocks.append({"type": "figure", "figure": figures[0]})
    slot = TABLE_SLOTS.get(artifact_id, {}).get(4)
    if slot is not None and slot < len(tables):
        blocks.append({"type": "table", **tables[slot]})
    blocks.append({"type": "paragraph", "text": narrative.get("trend_analysis", "")})
    return blocks


def build_page_five_blocks(artifact_id: str, figures: list, tables: list[dict], narrative: dict, df: pd.DataFrame) -> list[dict]:
    blocks = []
    if len(figures) > 1:
        blocks.append({"type": "figure", "figure": figures[1]})
    slot = TABLE_SLOTS.get(artifact_id, {}).get(5)
    if slot is not None and slot < len(tables):
        blocks.append({"type": "table", **tables[slot]})
    blocks.append({"type": "table", "title": "One Cikan Risk Basliklari", "headers": ["Baslik", "Yorum"], "rows": [[f"Risk {idx}", text] for idx, text in enumerate(extract_key_points(narrative.get("risk_analysis", ""))[:5], start=1)]})
    blocks.append({"type": "paragraph", "text": narrative.get("risk_analysis", "")})
    if len(figures) > 2:
        blocks.append({"type": "figure", "figure": figures[2]})
    return blocks


def build_data_scope(df: pd.DataFrame, source_files: list[str], warnings: list[dict], filter_summary: dict) -> dict[str, str]:
    scope = {
        "Toplam kayit sayisi": str(len(df)),
        "Kaynak dosya sayisi": str(len(source_files)),
        "Tarih araligi": describe_period(df),
        "Filtre uygulandi": "Evet" if filter_summary.get("applied") else "Hayir",
        "Filtre sonrasi satir": str(filter_summary.get("filtered_row_count") or len(df)),
        "Warning sayisi": str(len(warnings)),
    }
    if "direction" in df.columns:
        scope["Gelir kaydi"] = str(int((df["direction"] == "income").sum()))
        scope["Gider kaydi"] = str(int((df["direction"] == "expense").sum()))
    if filter_summary.get("summary_lines"):
        scope["Filtre ozeti"] = " | ".join(str(item) for item in filter_summary.get("summary_lines", []))
    return scope


def describe_period(df: pd.DataFrame) -> str:
    if "date" not in df.columns:
        return "Donem bilgisi yok"
    dates = pd.to_datetime(df["date"], errors="coerce").dropna()
    if dates.empty:
        return "Donem bilgisi yok"
    return f"{dates.min().strftime('%d.%m.%Y')} - {dates.max().strftime('%d.%m.%Y')}"


def build_metric_items(summary: dict, limit: int) -> list[dict]:
    items = []
    for key, value in summary.items():
        if value in (None, "", False):
            continue
        items.append({"label": prettify_label(key), "value": format_metric_value(value)})
    return items[:limit]


def build_methodology_items(df: pd.DataFrame, filter_summary: dict, warnings: list[dict]) -> list[tuple[str, str]]:
    return [
        ("Girdi satir sayisi", str(filter_summary.get("input_row_count") or len(df))),
        ("Filtre sonrasi satir", str(filter_summary.get("filtered_row_count") or len(df))),
        ("Uyari sayisi", str(len(warnings))),
        ("Hesaplama motoru", "Python / pandas"),
        ("Yorumlama katmani", "LLM yalnizca aciklayici anlatim icin kullanildi"),
    ]


def build_data_quality_callout(warnings: list[dict], filter_summary: dict, user_prompt: str | None) -> str:
    parts = []
    if user_prompt:
        parts.append(f"Kullanici istegi: {user_prompt}")
    if filter_summary.get("summary_lines"):
        parts.append("Filtre ozeti: " + " | ".join(str(item) for item in filter_summary.get("summary_lines", [])))
    if warnings:
        parts.append(f"Normalize ve birlesim asamasinda {len(warnings)} adet warning olustu.")
    if not parts:
        parts.append("Veri seti temel kalite kontrollerinden gecirildi ve normalize edilmis kayitlar rapora dahil edildi.")
    return " ".join(parts)


def extract_key_points(text: str) -> list[str]:
    lines = []
    for chunk in str(text or "").replace("\r", "\n").split("\n"):
        cleaned = chunk.strip(" -*\t")
        if cleaned:
            lines.append(cleaned)
    if not lines and text:
        return [segment.strip() for segment in str(text).split(". ") if segment.strip()]
    return lines


def build_analysis_figures(artifact_id: str, df: pd.DataFrame) -> list:
    builders = {
        "financial_risk_analysis": financial_figures,
        "cash_runway_analysis": cash_runway_figures,
        "anomaly_spending_analysis": anomaly_figures,
        "expense_optimization_analysis": expense_figures,
        "profitability_analysis": profitability_figures,
        "receivable_debt_risk_analysis": receivable_debt_figures,
        "sales_risk_analysis": sales_figures,
        "tax_risk_analysis": tax_figures,
    }
    builder = builders.get(artifact_id)
    return builder(df.copy()) if builder else []


def financial_figures(df: pd.DataFrame) -> list:
    figures = []
    frame = prepare_dates(df)
    if {"date", "direction", "amount"}.issubset(frame.columns):
        monthly = frame.pivot_table(index=frame["date"].dt.to_period("M"), columns="direction", values="amount", aggfunc="sum", fill_value=0)
        if not monthly.empty:
            fig, ax = plt.subplots(figsize=(10, 5))
            monthly.plot(kind="bar", ax=ax, color=["#15803D", "#B91C1C"])
            ax.set_title("Aylik Gelir ve Gider Trendi", loc="left", fontsize=14, fontweight="bold")
            ax.set_xlabel("Donem")
            ax.set_ylabel("Tutar")
            figures.append(fig)
        signed = frame["amount"].where(frame["direction"] == "income", -frame["amount"].abs())
        daily = signed.groupby(frame["date"].dt.date).sum()
        if not daily.empty:
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(daily.index.astype(str), daily.values, color="#2563EB", linewidth=2.5)
            ax.set_title("Gunluk Net Pozisyon", loc="left", fontsize=14, fontweight="bold")
            ax.set_xlabel("Gun")
            ax.set_ylabel("Net Tutar")
            ax.tick_params(axis="x", rotation=25)
            figures.append(fig)
    return figures


def cash_runway_figures(df: pd.DataFrame) -> list:
    figures = financial_figures(df)
    frame = prepare_dates(df)
    if {"date", "direction", "amount"}.issubset(frame.columns):
        expense = frame.loc[frame["direction"] == "expense"]
        if not expense.empty:
            daily_burn = expense.groupby(expense["date"].dt.date)["amount"].sum()
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.bar(daily_burn.index.astype(str), daily_burn.values, color="#DC2626")
            ax.set_title("Gunluk Burn Rate", loc="left", fontsize=14, fontweight="bold")
            ax.tick_params(axis="x", rotation=25)
            figures.append(fig)
    return figures[:3]


def anomaly_figures(df: pd.DataFrame) -> list:
    figures = []
    frame = df.loc[df.get("direction") == "expense"] if "direction" in df.columns else df.copy()
    if frame.empty:
        return figures
    top = frame.sort_values("amount", ascending=False).head(10)
    fig, ax = plt.subplots(figsize=(10, 5))
    labels = (top.get("description") if "description" in top.columns else top.get("category")).fillna("-")
    ax.barh(labels.astype(str), top["amount"].astype(float), color="#B91C1C")
    ax.set_title("En Yuksek Harcamalar", loc="left", fontsize=14, fontweight="bold")
    figures.append(fig)
    if "category" in frame.columns:
        cat = frame.groupby("category")["amount"].sum().sort_values(ascending=False).head(8)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(cat.index.astype(str), cat.values.astype(float), color="#2563EB")
        ax.set_title("Kategori Bazli Harcama Dagilimi", loc="left", fontsize=14, fontweight="bold")
        ax.tick_params(axis="x", rotation=25)
        figures.append(fig)
    return figures


def expense_figures(df: pd.DataFrame) -> list:
    figures = anomaly_figures(df)
    frame = prepare_dates(df.loc[df.get("direction") == "expense"] if "direction" in df.columns else df.copy())
    if {"date", "amount"}.issubset(frame.columns):
        monthly = frame.groupby(frame["date"].dt.to_period("M"))["amount"].sum()
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(monthly.index.astype(str), monthly.values.astype(float), color="#7C3AED", linewidth=2.5)
        ax.set_title("Aylik Gider Trend", loc="left", fontsize=14, fontweight="bold")
        figures.append(fig)
    return figures[:3]


def profitability_figures(df: pd.DataFrame) -> list:
    return financial_figures(df)


def receivable_debt_figures(df: pd.DataFrame) -> list:
    figures = []
    frame = df.copy()
    direction_field = "transaction_direction" if "transaction_direction" in frame.columns else "direction"
    party_field = "counterparty" if "counterparty" in frame.columns else "customer" if "customer" in frame.columns else None
    if party_field and direction_field in frame.columns:
        grouped = frame.pivot_table(index=party_field, columns=direction_field, values="amount", aggfunc="sum", fill_value=0).head(10)
        fig, ax = plt.subplots(figsize=(10, 5))
        grouped.plot(kind="bar", ax=ax)
        ax.set_title("Cari Bazli Borc / Alacak", loc="left", fontsize=14, fontweight="bold")
        ax.tick_params(axis="x", rotation=25)
        figures.append(fig)
    if "due_date" in frame.columns:
        due_dates = pd.to_datetime(frame["due_date"], errors="coerce")
        overdue_days = (pd.Timestamp.today().normalize() - due_dates).dt.days
        buckets = [
            int(((overdue_days >= 0) & (overdue_days <= 30)).sum()),
            int(((overdue_days >= 31) & (overdue_days <= 60)).sum()),
            int(((overdue_days >= 61) & (overdue_days <= 90)).sum()),
            int((overdue_days > 90).sum()),
        ]
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.bar(["0-30", "31-60", "61-90", "90+"], buckets, color="#EA580C")
        ax.set_title("Aging Bucket Dagilimi", loc="left", fontsize=14, fontweight="bold")
        figures.append(fig)
    return figures


def sales_figures(df: pd.DataFrame) -> list:
    figures = []
    frame = prepare_dates(df)
    value_field = "total_sales" if "total_sales" in frame.columns else "amount"
    if {"date", value_field}.issubset(frame.columns):
        monthly = frame.groupby(frame["date"].dt.to_period("M"))[value_field].sum()
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(monthly.index.astype(str), monthly.values.astype(float), color="#2563EB", linewidth=2.5)
        ax.set_title("Aylik Satis Trendi", loc="left", fontsize=14, fontweight="bold")
        figures.append(fig)
    for field, title in [("product_name", "Urun Performansi"), ("customer", "Musteri Performansi")]:
        if field in frame.columns:
            top = frame.groupby(field)[value_field].sum().sort_values(ascending=False).head(8)
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.barh(top.index.astype(str), top.values.astype(float), color="#0F766E")
            ax.set_title(title, loc="left", fontsize=14, fontweight="bold")
            figures.append(fig)
    return figures[:3]


def tax_figures(df: pd.DataFrame) -> list:
    figures = []
    frame = prepare_dates(df)
    if {"tax_type", "tax_amount"}.issubset(frame.columns):
        dist = frame.groupby("tax_type")["tax_amount"].sum().sort_values(ascending=False)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.pie(dist.values.astype(float), labels=dist.index.astype(str), autopct="%1.1f%%", startangle=90)
        ax.set_title("Vergi Turu Dagilimi", loc="left", fontsize=14, fontweight="bold")
        figures.append(fig)
    if {"date", "tax_amount"}.issubset(frame.columns):
        monthly = frame.groupby(frame["date"].dt.to_period("M"))["tax_amount"].sum()
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(monthly.index.astype(str), monthly.values.astype(float), color="#B91C1C", linewidth=2.5)
        ax.set_title("Aylik Vergi Yuku", loc="left", fontsize=14, fontweight="bold")
        figures.append(fig)
    return figures


def prepare_dates(df: pd.DataFrame) -> pd.DataFrame:
    frame = df.copy()
    if "date" in frame.columns:
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        if hasattr(frame["date"].dt, "tz") and frame["date"].dt.tz is not None:
            frame["date"] = frame["date"].dt.tz_localize(None)
        frame = frame.dropna(subset=["date"])
    return frame


# prettify_label is imported from services.localization_service


def format_metric_value(value) -> str:
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(value)
