from __future__ import annotations

import pandas as pd

from analyses.base_analysis_agent import BaseAnalysisAgent


class SalesRiskAnalysisAgent(BaseAnalysisAgent):
    artifact_id = "sales_risk_analysis"
    display_name = "Satış Risk ve Performans Analizi"

    def build_analysis(self, df: pd.DataFrame, user_prompt: str | None = None) -> dict:
        self._require_rows(df)
        frame = df.copy()
        value_field = "total_sales" if "total_sales" in frame.columns else "amount"
        customer_field = "customer" if "customer" in frame.columns else "customer_name"
        product_field = "product_name" if "product_name" in frame.columns else "product"
        total_sales = float(frame[value_field].sum())
        customer_share = frame.groupby(customer_field)[value_field].sum().sort_values(ascending=False) if customer_field in frame.columns else pd.Series(dtype=float)
        product_share = frame.groupby(product_field)[value_field].sum().sort_values(ascending=False) if product_field in frame.columns else pd.Series(dtype=float)
        metrics = {
            "toplam_satis": round(total_sales, 2),
            "en_buyuk_musteri_yogunlasma": round(float(customer_share.iloc[0] / total_sales * 100), 2) if not customer_share.empty and total_sales else 0.0,
            "en_buyuk_urun_yogunlasma": round(float(product_share.iloc[0] / total_sales * 100), 2) if not product_share.empty and total_sales else 0.0,
            "musteri_sayisi": int(frame[customer_field].nunique()) if customer_field in frame.columns else 0,
        }
        rows = [[str(idx), f"{float(val):,.2f}"] for idx, val in customer_share.head(10).items()]
        narrative = self.generate_narrative({"artifact_id": self.artifact_id, "metrics": metrics, "user_prompt": user_prompt})
        return {"title": self.display_name, "summary": metrics, "narrative": narrative, "tables": [{"title": "Müşteri Bazlı Satışlar", "headers": ["Müşteri", "Toplam Satış"], "rows": rows}]}
