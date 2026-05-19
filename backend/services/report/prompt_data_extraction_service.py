from __future__ import annotations

import re

from services.llm_service import LLMService


MONTHS = {
    "ocak": "Ocak",
    "subat": "Şubat",
    "şubat": "Şubat",
    "mart": "Mart",
    "nisan": "Nisan",
    "mayis": "Mayıs",
    "mayıs": "Mayıs",
    "haziran": "Haziran",
    "temmuz": "Temmuz",
    "agustos": "Ağustos",
    "ağustos": "Ağustos",
    "eylul": "Eylül",
    "eylül": "Eylül",
    "ekim": "Ekim",
    "kasim": "Kasım",
    "kasım": "Kasım",
    "aralik": "Aralık",
    "aralık": "Aralık",
}


EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "records": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "period": {"type": "string"},
                    "income": {"type": "number"},
                    "expense": {"type": "number"},
                    "category": {"type": "string"},
                    "amount": {"type": "number"},
                    "direction": {"type": "string"},
                },
                "additionalProperties": True,
            },
        }
    },
    "required": ["records"],
}


def parse_money_value(raw: str) -> float:
    text = raw.lower().replace("tl", "").replace("₺", "").strip()
    multiplier = 1
    if "milyon" in text:
        multiplier = 1_000_000
        text = text.replace("milyon", "")
    if "bin" in text:
        multiplier = 1_000
        text = text.replace("bin", "")
    text = text.replace(".", "").replace(",", ".")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        raise ValueError(f"Sayisal deger ayrismadi: {raw}")
    return float(match.group()) * multiplier


def extract_chart_data_from_prompt(user_prompt: str, artifact_id: str) -> list[dict]:
    prompt = (user_prompt or "").strip()
    if not prompt:
        return []

    llm_records = _extract_with_llm(prompt, artifact_id)
    if llm_records:
        return llm_records

    records = _extract_with_regex(prompt)
    return records


def _extract_with_llm(user_prompt: str, artifact_id: str) -> list[dict]:
    try:
        payload = LLMService().generate_json(
            prompt=(
                "Finansal grafik icin yalnizca yapisal veri cikar. "
                "Turkce aciklama yazma. JSON disinda hicbir sey donme.\n\n"
                f"artifact_id: {artifact_id}\n"
                f"user_prompt: {user_prompt}"
            ),
            response_schema=EXTRACTION_SCHEMA,
        )
    except Exception:
        return []
    records = payload.get("records")
    return records if isinstance(records, list) else []


def _extract_with_regex(user_prompt: str) -> list[dict]:
    normalized = user_prompt.replace("\n", " ")
    records: list[dict] = []

    monthly_pattern = re.compile(
        r"(?P<period>ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik)"
        r"[^.]*?(?:gelir|gelirim)\s*(?P<income>[\d.,\s]+(?:milyon|bin)?(?:\s*tl)?)"
        r"[^.]*?(?:gider|giderim)\s*(?P<expense>[\d.,\s]+(?:milyon|bin)?(?:\s*tl)?)",
        re.IGNORECASE,
    )
    for match in monthly_pattern.finditer(normalized):
        period_key = match.group("period").lower()
        records.append(
            {
                "period": MONTHS.get(period_key, match.group("period").title()),
                "income": parse_money_value(match.group("income")),
                "expense": parse_money_value(match.group("expense")),
            }
        )

    if records:
        return records

    income_match = re.search(r"(?:gelir|gelirim)\s*([\d.,\s]+(?:milyon|bin)?(?:\s*tl)?)", normalized, re.IGNORECASE)
    expense_match = re.search(r"(?:gider|giderim)\s*([\d.,\s]+(?:milyon|bin)?(?:\s*tl)?)", normalized, re.IGNORECASE)
    if income_match or expense_match:
        return [
            {
                "period": "Toplam",
                "income": parse_money_value(income_match.group(1)) if income_match else 0.0,
                "expense": parse_money_value(expense_match.group(1)) if expense_match else 0.0,
            }
        ]

    generic_pattern = re.compile(r"(gelir|gider)\s*([\d.,\s]+(?:milyon|bin)?(?:\s*tl)?)", re.IGNORECASE)
    generic_records = []
    for direction, amount in generic_pattern.findall(normalized):
        generic_records.append(
            {
                "direction": "income" if direction.lower().startswith("gelir") else "expense",
                "amount": parse_money_value(amount),
            }
        )
    return generic_records
