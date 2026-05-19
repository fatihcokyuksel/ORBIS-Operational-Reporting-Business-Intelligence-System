from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd

from config import settings
from utils.text_numbers import parse_numeric_value


ZERO = Decimal("0")
MONEY_QUANTUM = Decimal("0.01")


def to_decimal(value, default: Decimal | None = None) -> Decimal | None:
    if value is None or value is pd.NA:
        return default
    if isinstance(value, Decimal):
        if value.is_nan():
            return default
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        if pd.isna(value):
            return default
        return Decimal(str(value))
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass

    parsed = parse_numeric_value(value)
    if parsed is None:
        return default
    if isinstance(parsed, float) and pd.isna(parsed):
        return default
    return Decimal(str(parsed))


def to_float(value, default: float | None = None) -> float | None:
    decimal_value = to_decimal(value)
    if decimal_value is None:
        return default
    return float(decimal_value)


def to_non_negative_float(value, default: float = 0.0) -> float:
    decimal_value = to_decimal(value)
    if decimal_value is None:
        return default
    return float(abs(decimal_value))


def quantize_money(value, quantum: Decimal = MONEY_QUANTUM) -> Decimal:
    decimal_value = to_decimal(value, default=ZERO) or ZERO
    return decimal_value.quantize(quantum, rounding=ROUND_HALF_UP)


def safe_decimal_divide(numerator, denominator) -> Decimal | None:
    numerator_value = to_decimal(numerator)
    denominator_value = to_decimal(denominator)
    if numerator_value is None or denominator_value in {None, ZERO}:
        return None
    return numerator_value / denominator_value


def safe_divide(numerator, denominator) -> Decimal | None:
    return safe_decimal_divide(numerator, denominator)


def round_money(value) -> float:
    return float(quantize_money(value))


def compare_money_values(left, right, tolerance: Decimal | None = None) -> bool:
    try:
        left_value = quantize_money(left)
        right_value = quantize_money(right)
    except (InvalidOperation, ValueError):
        return False
    if left_value.is_nan() or right_value.is_nan():
        return False
    allowed = tolerance or settings.WARNING_MISMATCH_TOLERANCE
    return abs(left_value - right_value) <= allowed


def normalize_tax_rate(value) -> Decimal | None:
    tax_rate = to_decimal(value)
    if tax_rate is None:
        return None
    if ZERO < tax_rate < Decimal("1"):
        return quantize_money(tax_rate * Decimal("100"))
    if Decimal("1") <= tax_rate <= Decimal("100"):
        return quantize_money(tax_rate)
    return None


def calculate_tax_amount(base_amount, tax_rate) -> Decimal:
    base_value = to_decimal(base_amount, default=ZERO) or ZERO
    rate_value = to_decimal(tax_rate, default=ZERO) or ZERO
    return quantize_money(base_value * rate_value / Decimal("100"))


def calculate_total_employer_cost(
    gross_salary,
    employer_cost=None,
    bonus=None,
    benefits=None,
    employer_extra_cost=None,
) -> tuple[Decimal, Decimal]:
    gross_value = to_decimal(gross_salary, default=ZERO) or ZERO
    employer_cost_value = to_decimal(employer_cost)
    if employer_cost_value is None:
        employer_cost_value = quantize_money(gross_value * settings.EMPLOYER_SGK_RATE)
    bonus_value = to_decimal(bonus, default=ZERO) or ZERO
    benefits_value = to_decimal(benefits, default=ZERO) or ZERO
    employer_extra_cost_value = to_decimal(employer_extra_cost, default=ZERO) or ZERO
    total_cost = quantize_money(
        gross_value
        + employer_cost_value
        + bonus_value
        + benefits_value
        + employer_extra_cost_value
    )
    return quantize_money(employer_cost_value), total_cost


def normalize_currency(value, default: str | None = None) -> str:
    try:
        if value is None or value is pd.NA or pd.isna(value):
            value = None
    except TypeError:
        pass
    text = str(value if value not in {None, ""} else (default or settings.DEFAULT_CURRENCY)).strip().upper()
    return text or settings.DEFAULT_CURRENCY


def normalize_report_numbers_for_export(value):
    if isinstance(value, Decimal):
        return float(quantize_money(value))
    if isinstance(value, dict):
        return {key: normalize_report_numbers_for_export(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_report_numbers_for_export(item) for item in value]
    if isinstance(value, tuple):
        return [normalize_report_numbers_for_export(item) for item in value]
    return value
