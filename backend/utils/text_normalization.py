import re
import unicodedata


def normalize_text_for_match(value) -> str:
    if value is None:
        return ""

    text = str(value).strip().lower()
    replacements = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "İ": "i",
        "Ğ": "g",
        "Ü": "u",
        "Ş": "s",
        "Ö": "o",
        "Ç": "c",
        "Ä±": "i",
        "ÄŸ": "g",
        "Ã¼": "u",
        "ÅŸ": "s",
        "Ã¶": "o",
        "Ã§": "c",
        "Ä°": "i",
        "Ä": "g",
        "Ãœ": "u",
        "Å": "s",
        "Ã–": "o",
        "Ã‡": "c",
        "Å": "s",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)

    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_any(value, keywords: list[str]) -> bool:
    normalized = normalize_text_for_match(value)
    return any(keyword in normalized for keyword in keywords)
