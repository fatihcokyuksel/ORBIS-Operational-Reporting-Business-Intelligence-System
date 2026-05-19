import re
from dataclasses import dataclass

import pandas as pd

from utils.text_normalization import normalize_text_for_match


HEADER_KEYWORDS = {
    "tarih",
    "date",
    "islem",
    "aciklama",
    "description",
    "borc",
    "debit",
    "alacak",
    "credit",
    "gelir",
    "income",
    "gider",
    "expense",
    "tutar",
    "amount",
    "miktar",
    "kategori",
    "category",
    "bakiye",
    "balance",
    "firma",
    "cari",
    "hesap",
}


@dataclass
class ParsedExcelTable:
    dataframe: pd.DataFrame
    header_row_index: int
    original_columns: list[str]


def read_excel_table(file_path: str, sheet_name: str) -> ParsedExcelTable:
    raw_df = pd.read_excel(file_path, sheet_name=sheet_name, header=None, engine="openpyxl")
    raw_df = raw_df.dropna(how="all").dropna(axis=1, how="all")

    if raw_df.empty:
        return ParsedExcelTable(pd.DataFrame(), 0, [])

    header_row_index = detect_header_row(raw_df)
    header_values = raw_df.iloc[header_row_index].tolist()
    columns = make_unique_columns(header_values)
    data_df = raw_df.iloc[header_row_index + 1 :].copy()
    data_df.columns = columns
    data_df = data_df.dropna(how="all").dropna(axis=1, how="all")

    data_df.columns = make_unique_columns(data_df.columns)
    data_df = strip_string_cells(data_df)

    return ParsedExcelTable(
        dataframe=data_df.reset_index(drop=True),
        header_row_index=int(header_row_index),
        original_columns=[str(value) for value in header_values],
    )


def detect_header_row(raw_df: pd.DataFrame, max_scan_rows: int = 30) -> int:
    scan_count = min(max_scan_rows, len(raw_df))
    best_index = 0
    best_score = float("-inf")

    for index in range(scan_count):
        row = raw_df.iloc[index]
        score = score_header_candidate(row)
        if score > best_score:
            best_score = score
            best_index = index

    return int(best_index)


def score_header_candidate(row: pd.Series) -> float:
    values = [value for value in row.tolist() if not pd.isna(value) and str(value).strip()]
    if not values:
        return -100

    normalized_values = [normalize_text_for_match(value) for value in values]
    keyword_hits = sum(
        1
        for value in normalized_values
        for keyword in HEADER_KEYWORDS
        if keyword in value.split() or keyword == value
    )
    text_like_count = sum(1 for value in values if not looks_like_number(value))
    unique_count = len(set(normalized_values))
    duplicate_penalty = max(0, len(values) - unique_count)

    return (keyword_hits * 5) + (text_like_count * 1.5) + len(values) - duplicate_penalty


def make_unique_columns(columns) -> list[str]:
    seen = {}
    cleaned = []
    for index, value in enumerate(columns):
        name = clean_column_name(value, index)
        base_name = name
        count = seen.get(base_name, 0)
        if count:
            name = f"{base_name}_{count + 1}"
        seen[base_name] = count + 1
        cleaned.append(name)
    return cleaned


def clean_column_name(value, index: int) -> str:
    if value is None or pd.isna(value):
        return f"column_{index + 1}"

    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    text = re.sub(r"\s+", " ", text)
    if not text or text.lower().startswith("unnamed"):
        return f"column_{index + 1}"
    return text


def strip_string_cells(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    for column in cleaned.columns:
        cleaned[column] = cleaned[column].map(lambda value: value.strip() if isinstance(value, str) else value)
    return cleaned


def looks_like_number(value) -> bool:
    if isinstance(value, (int, float)):
        return True
    text = str(value).strip()
    if not text:
        return False
    return bool(re.fullmatch(r"[-+]?\d+([\.,]\d+)?", text))
