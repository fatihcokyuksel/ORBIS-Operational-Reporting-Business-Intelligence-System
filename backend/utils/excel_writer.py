from __future__ import annotations

from pathlib import Path
from decimal import Decimal

import pandas as pd

from utils.date_utils import parse_date_value


def write_report_workbook(output_path: str | Path, sheets: list[dict], report_currency: str | None = None):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(path, engine="xlsxwriter", datetime_format="dd.mm.yyyy", date_format="dd.mm.yyyy") as writer:
        workbook = writer.book
        header_format = workbook.add_format(
            {
                "bold": True,
                "bg_color": "#1F2937",
                "font_color": "#FFFFFF",
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )
        text_format = workbook.add_format({"border": 1})
        date_format = workbook.add_format({"border": 1, "num_format": "dd.mm.yyyy"})
        currency_format = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
        red_currency_format = workbook.add_format({"border": 1, "font_color": "#C00000", "num_format": "#,##0.00"})
        number_format = workbook.add_format({"border": 1, "num_format": "#,##0.00"})
        red_number_format = workbook.add_format({"border": 1, "font_color": "#C00000", "num_format": "#,##0.00"})
        percentage_format = workbook.add_format({"border": 1, "num_format": "0.00%"})

        for spec in sheets:
            write_sheet(
                writer=writer,
                sheet_name=spec["name"],
                data=spec.get("data"),
                header_format=header_format,
                text_format=text_format,
                date_format=date_format,
                currency_format=currency_format,
                red_currency_format=red_currency_format,
                number_format=number_format,
                red_number_format=red_number_format,
                percentage_format=percentage_format,
                currency_columns=spec.get("currency_columns", []),
                date_columns=spec.get("date_columns", []),
                number_columns=spec.get("number_columns", []),
                percentage_columns=spec.get("percentage_columns", []),
                columns=spec.get("columns"),
            )


def write_sheet(
    writer,
    sheet_name: str,
    data,
    header_format,
    text_format,
    date_format,
    currency_format,
    red_currency_format,
    number_format,
    red_number_format,
    percentage_format,
    currency_columns: list[str],
    date_columns: list[str],
    number_columns: list[str],
    percentage_columns: list[str],
    columns: list[str] | None,
):
    worksheet = writer.book.add_worksheet(sheet_name)
    writer.sheets[sheet_name] = worksheet

    df = dataframe_from_data(data=data, columns=columns)
    if df.empty:
        if columns:
            for col_index, column_name in enumerate(columns):
                worksheet.write(0, col_index, column_name, header_format)
                worksheet.set_column(col_index, col_index, max(14, len(str(column_name)) + 2))
            worksheet.autofilter(0, 0, 0, len(columns) - 1)
        return

    for col_index, column_name in enumerate(df.columns):
        worksheet.write(0, col_index, column_name, header_format)

    for row_index, (_, row) in enumerate(df.iterrows(), start=1):
        for col_index, column_name in enumerate(df.columns):
            value = row[column_name]
            cell_format = resolve_format(
                column_name=column_name,
                value=value,
                text_format=text_format,
                date_format=date_format,
                currency_format=currency_format,
                red_currency_format=red_currency_format,
                number_format=number_format,
                red_number_format=red_number_format,
                percentage_format=percentage_format,
                currency_columns=currency_columns,
                date_columns=date_columns,
                number_columns=number_columns,
                percentage_columns=percentage_columns,
            )
            write_value(worksheet, row_index, col_index, value, cell_format, column_name, date_columns)

    worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

    for col_index, column_name in enumerate(df.columns):
        width = max(
            len(str(column_name)) + 2,
            max((len(display_cell_value(value)) for value in df[column_name].head(500)), default=0) + 2,
        )
        worksheet.set_column(col_index, col_index, min(max(width, 12), 40))


def dataframe_from_data(data, columns: list[str] | None) -> pd.DataFrame:
    if isinstance(data, pd.DataFrame):
        return data.copy()
    if data is None:
        return pd.DataFrame(columns=columns or [])
    if isinstance(data, dict):
        return pd.DataFrame([data], columns=columns)
    return pd.DataFrame(list(data), columns=columns)


def resolve_format(
    column_name: str,
    value,
    text_format,
    date_format,
    currency_format,
    red_currency_format,
    number_format,
    red_number_format,
    percentage_format,
    currency_columns: list[str],
    date_columns: list[str],
    number_columns: list[str],
    percentage_columns: list[str],
):
    if column_name in date_columns:
        return date_format
    if column_name in percentage_columns:
        return percentage_format
    if column_name in currency_columns:
        return red_currency_format if is_negative_number(value) else currency_format
    if column_name in number_columns:
        return red_number_format if is_negative_number(value) else number_format
    return text_format


def write_value(worksheet, row_index: int, col_index: int, value, cell_format, column_name: str, date_columns: list[str]):
    try:
        is_missing = value is None or bool(pd.isna(value))
    except TypeError:
        is_missing = value is None
    if is_missing:
        worksheet.write_blank(row_index, col_index, None, cell_format)
        return
    if column_name in date_columns:
        parsed = parse_date_value(value)
        if not pd.isna(parsed):
            if getattr(parsed, "tzinfo", None) is not None:
                parsed = parsed.tz_localize(None)
            worksheet.write_datetime(row_index, col_index, parsed.to_pydatetime(), cell_format)
            return
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        worksheet.write_number(row_index, col_index, float(value), cell_format)
        return
    worksheet.write(row_index, col_index, value, cell_format)


def is_negative_number(value) -> bool:
    try:
        return float(value) < 0
    except (TypeError, ValueError):
        return False


def display_cell_value(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d.%m.%Y")
    return str(value)
