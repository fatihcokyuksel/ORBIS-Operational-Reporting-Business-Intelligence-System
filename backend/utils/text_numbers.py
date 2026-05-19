import re


def parse_amount_text(value: str) -> float | None:
    if value is None:
        return None

    text = str(value).lower().strip()
    multiplier = 1
    if "milyon" in text:
        multiplier = 1_000_000
    elif "bin" in text:
        multiplier = 1_000

    text = text.replace("milyon", "").replace("bin", "")
    is_negative = text.startswith("-") or text.endswith("-") or "(" in text and ")" in text
    text = re.sub(r"[^\d,\.]", "", text)
    if not text:
        return None

    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")

    try:
        amount = float(text) * multiplier
        return -amount if is_negative else amount
    except ValueError:
        return None


def parse_numeric_value(value) -> float | None:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    return parse_amount_text(text)
