from __future__ import annotations

import json
import os

from config import GOOGLE_API_KEY
from services.llm_service import LLMService


ANALYSIS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {"type": "string"},
    },
    "required": ["analysis"],
}


class AIAnalysisService:
    def __init__(self, enabled: bool | None = None):
        self.enabled = analysis_enabled() if enabled is None else enabled

    def generate(self, report_definition: dict, report_result: dict) -> dict:
        if not self.enabled or not GOOGLE_API_KEY:
            return {"analysis": "", "warnings": []}

        try:
            llm = LLMService()
            result = llm.generate_json(
                prompt=build_analysis_prompt(report_definition, report_result),
                response_schema=ANALYSIS_RESPONSE_SCHEMA,
            )
        except Exception as exc:
            return {
                "analysis": "",
                "warnings": [f"Yapay zeka analizi oluşturulamadı: {exc}"],
            }

        return {
            "analysis": clean_analysis_text(result.get("analysis") or ""),
            "warnings": [],
        }


def analysis_enabled() -> bool:
    value = os.getenv("REPORT_AI_ANALYSIS_ENABLED", "1").strip().lower()
    return value not in {"0", "false", "hayir", "hayır", "no"}


def clean_analysis_text(value: str) -> str:
    lines = []
    for line in str(value).splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        cleaned = cleaned.lstrip("-•*0123456789. )")
        if cleaned:
            lines.append(cleaned)
    return " ".join(lines).strip()


def build_analysis_prompt(report_definition: dict, report_result: dict) -> str:
    context = report_result.get("analysis_context") or {
        "summary": report_result.get("summary", {}),
        "metrics": report_result.get("metrics", []),
    }
    payload = {
        "rapor_adi": report_definition.get("display_name"),
        "rapor_id": report_definition.get("report_id"),
        "analiz_context": context,
    }

    return f"""
Sen muhasebe ve finans ekipleri için profesyonel finansal rapor analizi hazırlayan bir asistansın.
Sadece Türkçe yaz. İngilizce ifade kullanma.
Yanıtı tek, sade ve kısa bir özet paragraf olarak yaz.
Madde işareti, numaralı liste, başlık, alt başlık, tablo veya satır satır format kullanma.
En fazla 4 cümle kur; finansal gözlem, temel risk ve uygulanabilir öneriyi doğal bir paragraf içinde birleştir.
Abartılı yorum yapma; sadece verilen metriklerden çıkarılabilen ölçülü bir değerlendirme üret.
JSON dışında hiçbir metin döndürme.

Girdi:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""
