from __future__ import annotations

import pandas as pd

from analyses.base_analysis_agent import BaseAnalysisAgent


class AnomalySpendingAnalysisAgent(BaseAnalysisAgent):
    artifact_id = "anomaly_spending_analysis"
    display_name = "Anormal Harcama Analizi"

    def build_analysis(self, df: pd.DataFrame, user_prompt: str | None = None) -> dict:
        frame = df.loc[df["direction"] == "expense"].copy() if "direction" in df.columns else df.copy()
        self._require_rows(frame)
        q1 = frame["amount"].quantile(0.25)
        q3 = frame["amount"].quantile(0.75)
        iqr = q3 - q1
        upper = q3 + 1.5 * iqr
        frame["z_score"] = (frame["amount"] - frame["amount"].mean()) / (frame["amount"].std(ddof=0) or 1)
        anomalies = frame[(frame["amount"] > upper) | (frame["z_score"].abs() > 2.5)].copy()
        metrics = {
            "toplam_gider_kaydi": int(len(frame)),
            "anomali_sayisi": int(len(anomalies)),
            "anomali_orani": round((len(anomalies) / len(frame)) * 100, 2) if len(frame) else 0.0,
            "en_yuksek_anomali_tutar": round(float(anomalies["amount"].max()), 2) if not anomalies.empty else None,
            "iqr_esik": round(float(upper), 2),
        }
        rows = [
            [
                str(row.get("date", "-")),
                str(row.get("description") or row.get("category") or "-"),
                f"{float(row.get('amount', 0)):,.2f}",
                f"{float(row.get('z_score', 0)):.2f}",
            ]
            for _, row in anomalies.head(20).iterrows()
        ]
        narrative = self.generate_narrative({"artifact_id": self.artifact_id, "metrics": metrics, "user_prompt": user_prompt})
        return {
            "title": self.display_name,
            "summary": metrics,
            "narrative": narrative,
            "tables": [{"title": "Şüpheli İşlemler", "headers": ["Tarih", "Açıklama", "Tutar", "Z-Skor"], "rows": rows}],
        }
