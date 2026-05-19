from __future__ import annotations

from decimal import Decimal

import pandas as pd

from config import settings
from utils.money_utils import ZERO, normalize_currency, quantize_money, round_money, to_decimal
from utils.warning_utils import append_invalid_value_warning


def decimal_series_sum(series: pd.Series) -> Decimal:
    total = ZERO
    for value in series.tolist():
        decimal_value = to_decimal(value, default=ZERO) or ZERO
        total += decimal_value
    return quantize_money(total)


def decimal_series_mean(series: pd.Series) -> Decimal:
    valid_values = [to_decimal(value, default=ZERO) or ZERO for value in series.tolist()]
    if not valid_values:
        return ZERO
    return quantize_money(sum(valid_values, ZERO) / Decimal(len(valid_values)))


def build_currency_summary(
    df: pd.DataFrame,
    *,
    amount_fields: list[str],
    warnings: list[dict],
    audit_context: dict | None = None,
    currency_field: str = "currency",
) -> dict:
    if currency_field not in df.columns:
        currencies = [settings.DEFAULT_CURRENCY]
        working_df = df.assign(**{currency_field: settings.DEFAULT_CURRENCY})
    else:
        working_df = df.copy()
        working_df[currency_field] = working_df[currency_field].map(lambda value: normalize_currency(value, settings.DEFAULT_CURRENCY))
        currencies = sorted(set(working_df[currency_field].dropna().tolist()))

    totals_by_currency = {}
    for currency in currencies:
        currency_group = working_df.loc[working_df[currency_field] == currency]
        totals_by_currency[currency] = {
            field: round_money(decimal_series_sum(currency_group[field])) if field in currency_group.columns else 0.0
            for field in amount_fields
        }

    mixed_currency_detected = len(currencies) > 1
    if mixed_currency_detected:
        append_invalid_value_warning(
            warnings,
            warning_type="mixed_currency",
            severity="critical",
            action="partitioned_by_currency",
            audit_context=audit_context,
            input_value=currencies,
            message="Farkli para birimleri conversion olmadan toplandi.",
        )

    return {
        "mixed_currency_detected": mixed_currency_detected,
        "currencies_detected": currencies,
        "totals_by_currency": totals_by_currency,
        "reporting_currency": currencies[0] if len(currencies) == 1 else settings.DEFAULT_CURRENCY,
    }
