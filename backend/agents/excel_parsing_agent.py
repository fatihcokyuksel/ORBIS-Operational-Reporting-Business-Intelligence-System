import os

import pandas as pd

from utils.excel_table_detector import read_excel_table


def parse_excel_full(file_path: str, sheet_name: str) -> pd.DataFrame:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Dosya bulunamadi: {file_path}")

    return read_excel_table(file_path, sheet_name).dataframe
