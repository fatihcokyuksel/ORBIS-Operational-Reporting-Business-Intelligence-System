from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from config import settings
from schemas.report_filters import FilterApplicationSummary, ReportFilterSpec
from services.report.report_filter_defaults import get_report_filter_defaults
from utils.date_utils import is_overdue, parse_date_value
from utils.money_utils import ZERO, to_decimal
from utils.validation import normalize_payment_status
from utils.warning_utils import append_invalid_value_warning


def apply_report_filters(
    df: pd.DataFrame,
    filter_spec: ReportFilterSpec,
    report_type: str,
    user_prompt: str | None = None,
) -> tuple[pd.DataFrame, list[dict], FilterApplicationSummary]:
    working_df = df.copy()
    warnings: list[dict] = []
    summary_lines: list[str] = []
    defaults = get_report_filter_defaults(report_type)
    input_row_count = len(working_df)
    applied_filter_count = 0
    skipped_filter_count = 0

    if not filter_spec.has_actionable_filters():
        summary = FilterApplicationSummary(
            applied=False,
            user_prompt=user_prompt,
            spec=filter_spec if user_prompt else None,
            summary_lines=list(filter_spec.notes),
            input_row_count=input_row_count,
            filtered_row_count=input_row_count,
        )
        return working_df, warnings, summary

    if filter_spec.date_range:
        filtered_df, applied, skipped, line = apply_date_range_filter(
            working_df,
            filter_spec=filter_spec,
            report_type=report_type,
            warnings=warnings,
        )
        working_df = filtered_df
        applied_filter_count += int(applied)
        skipped_filter_count += int(skipped)
        if line:
            summary_lines.append(line)

    for amount_filter in filter_spec.amount_filters:
        filtered_df, applied, skipped, line = apply_amount_filter(
            working_df,
            amount_filter=amount_filter,
            warnings=warnings,
        )
        working_df = filtered_df
        applied_filter_count += int(applied)
        skipped_filter_count += int(skipped)
        if line:
            summary_lines.append(line)

    for category_filter in filter_spec.category_filters:
        filtered_df, applied, skipped, line = apply_category_filter(
            working_df,
            category_filter=category_filter,
            warnings=warnings,
        )
        working_df = filtered_df
        applied_filter_count += int(applied)
        skipped_filter_count += int(skipped)
        if line:
            summary_lines.append(line)

    for status_filter in filter_spec.status_filters:
        filtered_df, applied, skipped, line = apply_status_filter(
            working_df,
            status_filter=status_filter,
            warnings=warnings,
        )
        working_df = filtered_df
        applied_filter_count += int(applied)
        skipped_filter_count += int(skipped)
        if line:
            summary_lines.append(line)

    if filter_spec.include_only_unpaid:
        filtered_df, applied, skipped, line = apply_unpaid_filter(
            working_df,
            status_field=defaults.get("status_field"),
            warnings=warnings,
        )
        working_df = filtered_df
        applied_filter_count += int(applied)
        skipped_filter_count += int(skipped)
        if line:
            summary_lines.append(line)

    if filter_spec.include_only_overdue:
        filtered_df, applied, skipped, line = apply_overdue_filter(
            working_df,
            due_date_field=defaults.get("overdue_date_field"),
            status_field=defaults.get("status_field"),
            warnings=warnings,
        )
        working_df = filtered_df
        applied_filter_count += int(applied)
        skipped_filter_count += int(skipped)
        if line:
            summary_lines.append(line)

    if filter_spec.ranking:
        filtered_df, applied, skipped, line = apply_ranking_filter(
            working_df,
            filter_spec=filter_spec,
            report_type=report_type,
            warnings=warnings,
        )
        working_df = filtered_df
        applied_filter_count += int(applied)
        skipped_filter_count += int(skipped)
        if line:
            summary_lines.append(line)

    if filter_spec.sort:
        working_df = apply_sorts(working_df, filter_spec.sort)

    if skipped_filter_count and applied_filter_count:
        append_invalid_value_warning(
            warnings,
            warning_type="filter_partially_applied",
            severity="warning",
            action="filter_partially_applied",
            message="Bazi filtreler eksik alanlar nedeniyle uygulanamadi.",
            context={"applied_filter_count": applied_filter_count, "skipped_filter_count": skipped_filter_count},
        )

    if len(working_df) == 0:
        append_invalid_value_warning(
            warnings,
            warning_type="filter_no_rows_remaining",
            severity="warning",
            action="filter_no_rows_remaining",
            message="Uygulanan filtrelerden sonra rapor uretecek veri kalmadi.",
        )

    summary = FilterApplicationSummary(
        applied=applied_filter_count > 0,
        user_prompt=user_prompt,
        spec=filter_spec,
        summary_lines=summary_lines or list(filter_spec.notes),
        input_row_count=input_row_count,
        filtered_row_count=len(working_df),
    )
    return working_df, warnings, summary


def apply_date_range_filter(
    df: pd.DataFrame,
    *,
    filter_spec: ReportFilterSpec,
    report_type: str,
    warnings: list[dict],
) -> tuple[pd.DataFrame, bool, bool, str | None]:
    date_range = filter_spec.date_range
    if date_range is None:
        return df, False, False, None

    defaults = get_report_filter_defaults(report_type)
    field_name = date_range.field or defaults.get("primary_date_field")
    if not field_name or field_name not in df.columns:
        append_missing_field_warning(warnings, field_name or "date", "Tarih filtresi")
        return df, False, True, None

    prepared_series = df[field_name].map(parse_filter_date)
    mask = pd.Series(True, index=df.index)
    if date_range.start_date:
        start_date = parse_filter_date(date_range.start_date)
        if start_date is not None:
            mask &= prepared_series.map(lambda value: value is not None and value >= start_date)
    if date_range.end_date:
        end_date = parse_filter_date(date_range.end_date)
        if end_date is not None:
            mask &= prepared_series.map(lambda value: value is not None and value <= end_date)

    line = build_date_summary_line(date_range)
    return df.loc[mask].copy(), True, False, line


def apply_amount_filter(
    df: pd.DataFrame,
    *,
    amount_filter,
    warnings: list[dict],
) -> tuple[pd.DataFrame, bool, bool, str | None]:
    if amount_filter.field not in df.columns:
        append_missing_field_warning(warnings, amount_filter.field, "Tutar filtresi")
        return df, False, True, None

    series = df[amount_filter.field].map(lambda value: float(to_decimal(value, default=ZERO) or ZERO))
    operator = amount_filter.operator
    if operator == ">":
        mask = series > float(amount_filter.value or 0)
    elif operator == ">=":
        mask = series >= float(amount_filter.value or 0)
    elif operator == "<":
        mask = series < float(amount_filter.value or 0)
    elif operator == "<=":
        mask = series <= float(amount_filter.value or 0)
    elif operator == "=":
        mask = series == float(amount_filter.value or 0)
    else:
        min_value = float(amount_filter.min_value or 0)
        max_value = float(amount_filter.max_value or 0)
        mask = (series >= min_value) & (series <= max_value)

    return df.loc[mask].copy(), True, False, build_amount_summary_line(amount_filter)


def apply_category_filter(df: pd.DataFrame, *, category_filter, warnings: list[dict]) -> tuple[pd.DataFrame, bool, bool, str | None]:
    if category_filter.field not in df.columns:
        append_missing_field_warning(warnings, category_filter.field, "Kategori filtresi")
        return df, False, True, None

    values = [str(value).strip() for value in category_filter.values if str(value).strip()]
    if not values:
        return df, False, True, None

    if category_filter.match_mode == "contains":
        mask = df[category_filter.field].fillna("").astype(str).map(
            lambda cell: any(value.lower() in cell.lower() for value in values)
        )
    else:
        normalized_values = {value.lower() for value in values}
        mask = df[category_filter.field].fillna("").astype(str).str.lower().isin(normalized_values)

    line = f"{category_filter.field}: {', '.join(values)}"
    return df.loc[mask].copy(), True, False, line


def apply_status_filter(df: pd.DataFrame, *, status_filter, warnings: list[dict]) -> tuple[pd.DataFrame, bool, bool, str | None]:
    if status_filter.field not in df.columns:
        append_missing_field_warning(warnings, status_filter.field, "Durum filtresi")
        return df, False, True, None

    normalized_values = {normalize_status_value(value) for value in status_filter.values}
    normalized_values.discard(None)
    if not normalized_values:
        return df, False, True, None

    mask = df[status_filter.field].map(normalize_status_value).isin(normalized_values)
    line = f"{status_filter.field}: {', '.join(sorted(normalized_values))}"
    return df.loc[mask].copy(), True, False, line


def apply_unpaid_filter(
    df: pd.DataFrame,
    *,
    status_field: str | None,
    warnings: list[dict],
) -> tuple[pd.DataFrame, bool, bool, str | None]:
    if not status_field or status_field not in df.columns:
        append_missing_field_warning(warnings, status_field or "payment_status", "Odenmemis filtresi")
        return df, False, True, None

    status_series = df[status_field].map(normalize_status_value)
    mask = status_series.isin({"unpaid", "partial", "open"})
    return df.loc[mask].copy(), True, False, "Sadece odenmemis/acik kayitlar"


def apply_overdue_filter(
    df: pd.DataFrame,
    *,
    due_date_field: str | None,
    status_field: str | None,
    warnings: list[dict],
) -> tuple[pd.DataFrame, bool, bool, str | None]:
    if not due_date_field or due_date_field not in df.columns:
        append_missing_field_warning(warnings, due_date_field or "due_date", "Vadesi gecmis filtresi")
        return df, False, True, None

    mask = df[due_date_field].map(lambda value: is_overdue(value, timezone_value=settings.DEFAULT_TIMEZONE))
    if status_field and status_field in df.columns:
        mask &= df[status_field].map(normalize_status_value) != "paid"
    return df.loc[mask].copy(), True, False, "Sadece vadesi gecmis kayitlar"


def apply_ranking_filter(
    df: pd.DataFrame,
    *,
    filter_spec: ReportFilterSpec,
    report_type: str,
    warnings: list[dict],
) -> tuple[pd.DataFrame, bool, bool, str | None]:
    ranking = filter_spec.ranking
    if ranking is None:
        return df, False, False, None

    if ranking.scope == "rows":
        if ranking.metric_field not in df.columns:
            append_missing_field_warning(warnings, ranking.metric_field, "Top-N filtresi")
            return df, False, True, None
        metric_series = df[ranking.metric_field].map(lambda value: float(to_decimal(value, default=ZERO) or ZERO))
        sorted_df = df.assign(__ranking_metric__=metric_series).sort_values(
            "__ranking_metric__",
            ascending=ranking.direction == "asc",
        )
        line = f"En buyuk {ranking.top_n} islem"
        return sorted_df.head(ranking.top_n).drop(columns=["__ranking_metric__"]), True, False, line

    missing_fields = [field_name for field_name in ranking.group_by if field_name not in df.columns]
    if missing_fields:
        for field_name in missing_fields:
            append_missing_field_warning(warnings, field_name, "Group Top-N filtresi")
        return df, False, True, None

    metric_frame = build_group_ranking_frame(df, ranking.group_by, ranking.metric_field, ranking.aggregate, report_type)
    if metric_frame.empty:
        return df.iloc[0:0].copy(), True, False, f"Top {ranking.top_n} grup sonucu veri kalmadi"

    sorted_frame = metric_frame.sort_values("__metric__", ascending=ranking.direction == "asc")
    selected = sorted_frame.head(ranking.top_n)
    selected_keys = set(tuple(row[field] for field in ranking.group_by) for _, row in selected.iterrows())

    mask = df[ranking.group_by].apply(lambda row: tuple(row[field] for field in ranking.group_by) in selected_keys, axis=1)
    label = ranking.group_by[0] if ranking.group_by else "grup"
    line = f"Top {ranking.top_n} {label}"
    return df.loc[mask].copy(), True, False, line


def build_group_ranking_frame(
    df: pd.DataFrame,
    group_by: list[str],
    metric_field: str,
    aggregate: str,
    report_type: str,
) -> pd.DataFrame:
    base = df[group_by].copy()
    if aggregate == "risk_score" or metric_field == "risk_score":
        base["__metric__"] = df.apply(lambda row: float(compute_risk_score(row, report_type)), axis=1)
        return base.groupby(group_by, dropna=False, as_index=False)["__metric__"].sum()

    if aggregate == "count":
        return base.groupby(group_by, dropna=False, as_index=False).size().rename(columns={"size": "__metric__"})

    numeric_series = df[metric_field].map(lambda value: float(to_decimal(value, default=ZERO) or ZERO))
    working = df.assign(__metric_source__=numeric_series)
    grouped = working.groupby(group_by, dropna=False)["__metric_source__"]
    if aggregate == "mean":
        metric_values = grouped.mean()
    elif aggregate == "max":
        metric_values = grouped.max()
    elif aggregate == "min":
        metric_values = grouped.min()
    else:
        metric_values = grouped.sum()
    return metric_values.reset_index().rename(columns={"__metric_source__": "__metric__"})


def compute_risk_score(row: pd.Series, report_type: str):
    amount = to_decimal(row.get("amount"), default=ZERO) or ZERO
    status_value = normalize_status_value(row.get("payment_status"))
    if status_value == "paid":
        return ZERO

    due_value = row.get("due_date")
    if due_value and not is_overdue(due_value, timezone_value=settings.DEFAULT_TIMEZONE):
        return ZERO

    counterparty_type = str(row.get("counterparty_type") or "").lower()
    direction_value = str(row.get("direction") or row.get("transaction_direction") or "").lower()

    if report_type == "debt_receivable_report":
        if counterparty_type == "customer":
            return amount if direction_value == "receivable" else ZERO
        if counterparty_type == "supplier":
            return amount if direction_value == "debt" else ZERO
    if report_type == "current_account_report":
        if counterparty_type == "customer":
            return amount if direction_value == "receivable" else ZERO
        if counterparty_type == "supplier":
            return amount if direction_value == "debt" else ZERO

    return amount


def apply_sorts(df: pd.DataFrame, sort_specs: Iterable) -> pd.DataFrame:
    working_df = df.copy()
    for index, sort_spec in enumerate(reversed(list(sort_specs))):
        field_name = sort_spec.field
        helper_column = f"__sort_{index}__"
        working_df[helper_column] = working_df[field_name].map(prepare_sort_value)
        working_df = working_df.sort_values(helper_column, ascending=sort_spec.direction == "asc", na_position="last")
        working_df = working_df.drop(columns=[helper_column])
    return working_df


def parse_filter_date(value) -> pd.Timestamp | None:
    parsed = parse_date_value(value, timezone_value=settings.DEFAULT_TIMEZONE)
    if pd.isna(parsed):
        return None
    return parsed


def normalize_status_value(value) -> str | None:
    normalized = normalize_payment_status(value)
    if normalized is not None:
        return normalized
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().lower()
    return text or None


def prepare_sort_value(value):
    parsed_date = parse_filter_date(value)
    if parsed_date is not None:
        return parsed_date
    decimal_value = to_decimal(value)
    if decimal_value is not None:
        return float(decimal_value)
    if value is None:
        return ""
    return str(value).lower()


def append_missing_field_warning(warnings: list[dict], field_name: str, message_prefix: str):
    append_invalid_value_warning(
        warnings,
        warning_type="filter_field_missing",
        severity="warning",
        field=field_name,
        action="filter_skipped",
        message=f"{message_prefix} icin alan bulunamadi: {field_name}",
    )


def build_date_summary_line(date_range) -> str:
    parts = []
    if date_range.start_date:
        parts.append(date_range.start_date)
    if date_range.end_date:
        parts.append(date_range.end_date)
    if not parts and date_range.relative_range:
        return date_range.relative_range
    return "Tarih: " + " - ".join(parts)


def build_amount_summary_line(amount_filter) -> str:
    if amount_filter.operator == "between":
        return f"{amount_filter.field} {amount_filter.min_value} ile {amount_filter.max_value} arasi"
    return f"{amount_filter.field} {amount_filter.operator} {amount_filter.value}"
