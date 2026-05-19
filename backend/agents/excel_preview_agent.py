import os 
import json
import warnings
import pandas as pd

from config import settings
from utils.excel_table_detector import read_excel_table
from utils.security_utils import mask_sensitive_payload
from utils.text_numbers import parse_numeric_value


def make_json_safe_value(value):
    """
    pandas/numpy değerlerini json'a uygun hale getirir.
    """
    if pd.isna(value):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    
    return value


def dataframe_to_sample_rows(df: pd.DataFrame, sample_size: int = 5):
    """
    ilk 5, son 5, rastgele 5 satırdan örnek veri üretir
    amacı, llm'e tüm exceli değil dosyanın yapısını göstermek.
    """
    if df.empty:
        return []
    
    samples = []

    head_df = df.head(sample_size)
    tail_df = df.tail(sample_size)

    if len(df) > sample_size:
        random_df = df.sample(min(sample_size, len(df)), random_state=42)
        sample_df = pd.concat([head_df, tail_df, random_df])
    else:
        sample_df = head_df

    sample_df = sample_df.drop_duplicates()

    for _, row in sample_df.iterrows():
        row_dict = {}
        for col in df.columns:
            row_dict[str(col)] = make_json_safe_value(row[col])
        samples.append(row_dict)

    return samples


def detect_column_types(df: pd.DataFrame):
    """
    kolonları basitçe numeric/date/text olarak sınıflandırır.
    llm'e yardımcı olarak verilir.
    """
    
    numeric_columns = []
    date_like_columns = []
    text_columns = []

    for col in df.columns:
        series = df[col].dropna()

        if series.empty:
            text_columns.append(str(col))
            continue

        date_ratio = detect_date_ratio(series)
        numeric_converted = series.map(parse_numeric_value)
        numeric_ratio = numeric_converted.notna().mean()

        if date_ratio >= 0.7:
            date_like_columns.append(str(col))
        elif numeric_ratio >= 0.7:
            numeric_columns.append(str(col))
        else:
            text_columns.append(str(col))

    return {
        "numeric_columns": numeric_columns,
        "date_like_columns": date_like_columns,
        "text_columns": text_columns
    }


def detect_date_ratio(series: pd.Series) -> float:
    if pd.api.types.is_datetime64_any_dtype(series):
        return 1.0

    candidates = series[
        series.map(
            lambda value: hasattr(value, "year")
            or any(separator in str(value) for separator in ["-", "/", "."])
        )
    ]
    if candidates.empty:
        return 0.0

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        converted = pd.to_datetime(candidates, errors="coerce", dayfirst=True)

    return float(converted.notna().mean())


def clean_columns(columns):
    """
    kolon isimlerini stringe çevirir ve baş/son boşlukları temizler
    """
    cleaned = []
    for col in columns:
        if col is None:
            cleaned.append("")
        else:
            cleaned.append(str(col).strip())

    return cleaned


def create_excel_preview_json(file_path: str, sample_size: int = 5):
    """
    excel dosyasını analiz eder ve llm'e gönderilecek preview json'u üretir
    bu fonksiyonun amacı okunan raporun yapısını çıkartmaktır.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dosya bulunamadı: {file_path}")
    
    with pd.ExcelFile(file_path) as excel_file:
        preview_json = {
            "file_name": os.path.basename(file_path),
            "file_path": file_path,
            "sheet_count": len(excel_file.sheet_names),
            "sheets": []
        }

        for sheet_name in excel_file.sheet_names:
            parsed_table = read_excel_table(file_path, sheet_name)
            df = parsed_table.dataframe

            column_types = detect_column_types(df)

            sheet_preview = {
                "sheet_name": sheet_name,
                "detected_header_row_index": parsed_table.header_row_index,
                "original_header_values": parsed_table.original_columns,
                "row_count": int(len(df)),
                "column_count": int(len(df.columns)),
                "columns": [str(col) for col in df.columns],
                "sample_rows": dataframe_to_sample_rows(df, sample_size=sample_size),
                "numeric_columns": column_types["numeric_columns"],
                "date_like_columns": column_types["date_like_columns"],
                "text_columns": column_types["text_columns"]
            }

            preview_json["sheets"].append(sheet_preview)

    return preview_json
        

def save_preview_json(preview_json: dict, output_path: str):
    """
    debugging için preview json'u dosyaya kaydeder.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    payload = mask_sensitive_payload(preview_json) if settings.MASK_SENSITIVE_DEBUG else preview_json

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)




