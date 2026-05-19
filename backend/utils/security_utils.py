from __future__ import annotations

import re


def mask_iban(value) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    compact = re.sub(r"\s+", "", text)
    if len(compact) <= 8:
        return compact
    return f"{compact[:4]} {'*' * 4} {'*' * 4} {compact[-4:]}"


def mask_tax_id(value) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}{'*' * max(len(text) - 4, 1)}{text[-2:]}"


def mask_employee_name(value) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    parts = [part for part in text.split() if part]
    if not parts:
        return None
    masked = []
    for part in parts:
        if len(part) == 1:
            masked.append("*")
        else:
            masked.append(f"{part[0]}{'*' * max(len(part) - 1, 1)}")
    return " ".join(masked)


def mask_sensitive_value(field_name: str, value):
    lowered = str(field_name or "").lower()
    if "iban" in lowered:
        return mask_iban(value)
    if any(keyword in lowered for keyword in ["tax_id", "taxid", "vergi", "vkn", "tckn", "kimlik"]):
        return mask_tax_id(value)
    if any(keyword in lowered for keyword in ["employee_name", "personel", "ad soyad", "name"]):
        return mask_employee_name(value)
    return value


def mask_sensitive_payload(payload):
    if isinstance(payload, list):
        return [mask_sensitive_payload(item) for item in payload]
    if isinstance(payload, dict):
        return {key: mask_sensitive_payload(mask_sensitive_value(key, value)) for key, value in payload.items()}
    return payload


def _clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
