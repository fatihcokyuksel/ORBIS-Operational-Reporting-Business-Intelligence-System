from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
import json
import re

from config import settings
from schemas.report_filters import (
    AmountFilter,
    CategoryFilter,
    DateRangeFilter,
    RankingSpec,
    ReportFilterSpec,
    SortSpec,
    StatusFilter,
)
from services.llm_service import LLMService
from services.report.report_filter_defaults import get_report_filter_defaults
from utils.date_utils import today_date
from utils.mapping_utils import match_field_by_alias
from utils.text_normalization import normalize_text_for_match
from utils.text_numbers import parse_amount_text


MONTHS = {
    "ocak": 1,
    "subat": 2,
    "mart": 3,
    "nisan": 4,
    "mayis": 5,
    "haziran": 6,
    "temmuz": 7,
    "agustos": 8,
    "eylul": 9,
    "ekim": 10,
    "kasim": 11,
    "aralik": 12,
}

DATE_RANGE_RE = re.compile(
    r"(?P<start>\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*(?:-|–|—)\s*(?P<end>\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
    re.IGNORECASE,
)
BETWEEN_AMOUNT_RE = re.compile(
    r"(?P<min>\d[\d\s.,]*(?:bin|milyon)?(?:\s*tl)?)\s*(?:ile|ve)\s*(?P<max>\d[\d\s.,]*(?:bin|milyon)?(?:\s*tl)?)\s*arasi",
    re.IGNORECASE,
)
TOP_N_RE = re.compile(r"en\s+(?:buyuk|buyuk\s+olan|yuksek)\s+(?P<count>\d+)", re.IGNORECASE)


def extract_report_filters(
    user_prompt: str,
    report_type: str,
    available_columns: list[str],
    normalized_schema: list[str],
    min_date: str | None = None,
    max_date: str | None = None,
) -> ReportFilterSpec:
    prompt = (user_prompt or "").strip()
    if not prompt:
        return ReportFilterSpec()

    llm_spec = try_extract_with_llm(
        user_prompt=prompt,
        report_type=report_type,
        available_columns=available_columns,
        normalized_schema=normalized_schema,
        min_date=min_date,
        max_date=max_date,
    )

    if llm_spec and llm_spec.has_actionable_filters():
        return sanitize_filter_spec(llm_spec, report_type, normalized_schema)

    fallback_spec = extract_with_fallback(prompt, report_type, normalized_schema)
    if fallback_spec.has_actionable_filters():
        if llm_spec and llm_spec.notes:
            fallback_spec.notes.extend(note for note in llm_spec.notes if note not in fallback_spec.notes)
        if not fallback_spec.confidence:
            fallback_spec.confidence = 0.55
        return sanitize_filter_spec(fallback_spec, report_type, normalized_schema)

    spec = sanitize_filter_spec(llm_spec or ReportFilterSpec(), report_type, normalized_schema)
    if "Dogrudan uygulanabilir filtre cikarilamadi." not in spec.notes:
        spec.notes.append("Dogrudan uygulanabilir filtre cikarilamadi.")
    spec.confidence = min(spec.confidence or 0.0, 0.35)
    return spec


def try_extract_with_llm(
    *,
    user_prompt: str,
    report_type: str,
    available_columns: list[str],
    normalized_schema: list[str],
    min_date: str | None,
    max_date: str | None,
) -> ReportFilterSpec | None:
    if not settings.GOOGLE_API_KEY:
        return None

    schema = ReportFilterSpec.model_json_schema()
    prompt = build_llm_prompt(
        user_prompt=user_prompt,
        report_type=report_type,
        available_columns=available_columns,
        normalized_schema=normalized_schema,
        min_date=min_date,
        max_date=max_date,
    )

    try:
        payload = LLMService().generate_json(prompt=prompt, response_schema=schema)
    except Exception as exc:
        return ReportFilterSpec(
            notes=[f"LLM filter extraction basarisiz oldu: {exc}"],
            confidence=0.0,
        )

    try:
        return ReportFilterSpec.model_validate(payload)
    except Exception:
        try:
            return ReportFilterSpec.model_validate(json.loads(json.dumps(payload)))
        except Exception as exc:
            return ReportFilterSpec(
                notes=[f"LLM filter spec parse edilemedi: {exc}"],
                confidence=0.0,
            )


def build_llm_prompt(
    *,
    user_prompt: str,
    report_type: str,
    available_columns: list[str],
    normalized_schema: list[str],
    min_date: str | None,
    max_date: str | None,
) -> str:
    today = today_date(settings.DEFAULT_TIMEZONE).isoformat()
    return f"""
Sen finansal rapor sistemi icin filtre cikarim agentisin.
Hesaplama yapma.
Rapor uretme.
Sadece kullanicinin dogal dilde yazdigi ozel istegi JSON filter spec'e donustur.

report_type:
{report_type}

normalized_schema:
{json.dumps(normalized_schema, ensure_ascii=False)}

available_columns:
{json.dumps(available_columns, ensure_ascii=False)}

min_date:
{min_date}

max_date:
{max_date}

user_prompt:
{user_prompt}

Kurallar:
- Sadece schema'da bulunan alanlari kullan.
- Emin degilsen notes icine yaz.
- Tarih araliklarini ISO formatina cevir.
- Goreli tarihleri bugunun tarihine gore coz.
- Bugunun tarihi: {today}
- Timezone: {settings.DEFAULT_TIMEZONE}
- Para ifadelerini sayiya cevir:
  - 50 bin = 50000
  - 1 milyon = 1000000
- JSON disinda hicbir metin dondurme.
"""


def sanitize_filter_spec(spec: ReportFilterSpec, report_type: str, normalized_schema: list[str]) -> ReportFilterSpec:
    if spec is None:
        return ReportFilterSpec()

    allowed_fields = set(normalized_schema)
    defaults = get_report_filter_defaults(report_type)
    notes = list(spec.notes)

    date_range = spec.date_range
    if date_range:
        resolved_field = resolve_field_name(date_range.field, normalized_schema, defaults.get("primary_date_field"))
        if resolved_field is None:
            notes.append("Tarih filtresi icin uygun alan bulunamadi.")
            date_range = None
        else:
            date_range.field = resolved_field

    amount_filters: list[AmountFilter] = []
    for amount_filter in spec.amount_filters:
        fallback_field = defaults.get("amount_field")
        resolved_field = resolve_field_name(amount_filter.field, normalized_schema, fallback_field)
        if resolved_field is None:
            notes.append(f"Tutar filtresi icin alan bulunamadi: {amount_filter.field}")
            continue
        amount_filter.field = resolved_field
        amount_filters.append(amount_filter)

    category_filters: list[CategoryFilter] = []
    for category_filter in spec.category_filters:
        resolved_field = resolve_field_name(category_filter.field, normalized_schema)
        if resolved_field is None:
            notes.append(f"Kategori filtresi icin alan bulunamadi: {category_filter.field}")
            continue
        category_filter.field = resolved_field
        category_filter.values = [value for value in category_filter.values if str(value).strip()]
        if category_filter.values:
            category_filters.append(category_filter)

    status_filters: list[StatusFilter] = []
    for status_filter in spec.status_filters:
        fallback_field = defaults.get("status_field")
        resolved_field = resolve_field_name(status_filter.field, normalized_schema, fallback_field)
        if resolved_field is None:
            notes.append(f"Durum filtresi icin alan bulunamadi: {status_filter.field}")
            continue
        status_filter.field = resolved_field
        status_filter.values = [str(value).strip().lower() for value in status_filter.values if str(value).strip()]
        if status_filter.values:
            status_filters.append(status_filter)

    sort_specs: list[SortSpec] = []
    for sort_spec in spec.sort:
        resolved_field = resolve_field_name(sort_spec.field, normalized_schema, defaults.get("amount_field"))
        if resolved_field is None:
            notes.append(f"Siralama alani bulunamadi: {sort_spec.field}")
            continue
        sort_spec.field = resolved_field
        sort_specs.append(sort_spec)

    ranking = sanitize_ranking_spec(spec.ranking, report_type, normalized_schema, notes)

    sanitized = ReportFilterSpec(
        date_range=date_range,
        amount_filters=amount_filters,
        category_filters=category_filters,
        status_filters=status_filters,
        sort=sort_specs,
        ranking=ranking,
        top_n=spec.top_n,
        include_only_overdue=spec.include_only_overdue,
        include_only_unpaid=spec.include_only_unpaid,
        notes=dedupe_notes(notes),
        confidence=max(0.0, min(spec.confidence or 0.0, 1.0)),
    )
    if sanitized.date_range and sanitized.date_range.field not in allowed_fields:
        sanitized.notes.append(f"Tarih alani normalize schema icinde degil: {sanitized.date_range.field}")
        sanitized.date_range = None
    return sanitized


def sanitize_ranking_spec(
    ranking: RankingSpec | None,
    report_type: str,
    normalized_schema: list[str],
    notes: list[str],
) -> RankingSpec | None:
    if ranking is None:
        return None

    defaults = get_report_filter_defaults(report_type)
    if ranking.scope == "rows":
        metric_field = resolve_field_name(ranking.metric_field, normalized_schema, defaults.get("amount_field"))
        if metric_field is None:
            notes.append(f"Rows ranking icin metric alani bulunamadi: {ranking.metric_field}")
            return None
        ranking.metric_field = metric_field
        return ranking

    ranking_dimensions = defaults.get("ranking_dimensions", {})
    resolved_group_by = [resolve_field_name(field_name, normalized_schema) for field_name in ranking.group_by]
    resolved_group_by = [field_name for field_name in resolved_group_by if field_name]

    if not resolved_group_by and ranking.metric_field in ranking_dimensions:
        resolved_group_by = list(ranking_dimensions[ranking.metric_field]["group_by"])

    if not resolved_group_by:
        matched_dimension = resolve_ranking_dimension(ranking.metric_field, ranking_dimensions)
        if matched_dimension:
            preset = ranking_dimensions[matched_dimension]
            ranking.group_by = list(preset["group_by"])
            ranking.metric_field = preset["metric_field"]
            ranking.aggregate = preset["aggregate"]
            ranking.direction = preset.get("direction", ranking.direction)
            return ranking
        notes.append("Group ranking icin uygun boyut bulunamadi.")
        return None

    dimension_match = resolve_ranking_dimension(resolved_group_by[0], ranking_dimensions)
    if dimension_match and ranking.metric_field != "risk_score" and ranking.aggregate != "risk_score":
        preset = ranking_dimensions[dimension_match]
        ranking.metric_field = preset["metric_field"]
        ranking.aggregate = preset["aggregate"]
        ranking.direction = preset.get("direction", ranking.direction)

    ranking.group_by = resolved_group_by
    if ranking.metric_field != "risk_score":
        metric_field = resolve_field_name(ranking.metric_field, normalized_schema, defaults.get("amount_field"))
        if metric_field is None:
            notes.append(f"Group ranking metric alani bulunamadi: {ranking.metric_field}")
            return None
        ranking.metric_field = metric_field
    return ranking


def resolve_ranking_dimension(candidate: str | None, ranking_dimensions: dict) -> str | None:
    if not candidate:
        return None
    if candidate in ranking_dimensions:
        return candidate
    normalized_candidate = normalize_text_for_match(candidate)
    for dimension in ranking_dimensions.keys():
        if normalize_text_for_match(dimension) == normalized_candidate:
            return dimension
    return None


def resolve_field_name(candidate: str | None, normalized_schema: list[str], fallback: str | None = None) -> str | None:
    if candidate and candidate in normalized_schema:
        return candidate
    if candidate:
        matched = match_field_by_alias(candidate, normalized_schema)
        if matched:
            return matched
        normalized_candidate = normalize_text_for_match(candidate)
        for field_name in normalized_schema:
            if normalize_text_for_match(field_name) == normalized_candidate:
                return field_name
    if fallback and fallback in normalized_schema:
        return fallback
    return None


def extract_with_fallback(user_prompt: str, report_type: str, normalized_schema: list[str]) -> ReportFilterSpec:
    defaults = get_report_filter_defaults(report_type)
    prompt_lower = user_prompt.lower()
    normalized_prompt = normalize_text_for_match(user_prompt)
    today = today_date(settings.DEFAULT_TIMEZONE)

    spec = ReportFilterSpec(confidence=0.55)

    date_range = extract_date_range(user_prompt, normalized_prompt, today, defaults.get("primary_date_field"))
    if date_range:
        spec.date_range = date_range

    between_match = BETWEEN_AMOUNT_RE.search(prompt_lower)
    if between_match:
        min_value = parse_amount_text(between_match.group("min"))
        max_value = parse_amount_text(between_match.group("max"))
        if min_value is not None and max_value is not None:
            spec.amount_filters.append(
                AmountFilter(
                    field=defaults.get("amount_field", "amount"),
                    operator="between",
                    min_value=min(min_value, max_value),
                    max_value=max(min_value, max_value),
                )
            )
    else:
        comparison_filter = extract_amount_comparison(prompt_lower, defaults.get("amount_field", "amount"))
        if comparison_filter:
            spec.amount_filters.append(comparison_filter)

    if any(token in normalized_prompt for token in ["odenmemis", "paid olmayan", "odeme yapilmamis", "acik alacak"]):
        spec.include_only_unpaid = True

    if "vadesi gecmis" in normalized_prompt:
        spec.include_only_overdue = True

    category_filter = extract_category_filter(user_prompt, normalized_prompt, report_type, normalized_schema)
    if category_filter is not None:
        spec.category_filters.append(category_filter)

    ranking = extract_ranking_filter(normalized_prompt, report_type, defaults)
    if ranking is not None:
        spec.ranking = ranking

    if "en riskli cari" in normalized_prompt and spec.ranking is None:
        spec.ranking = RankingSpec(
            scope="groups",
            group_by=["counterparty"],
            metric_field="risk_score",
            aggregate="risk_score",
            direction="desc",
            top_n=10,
        )

    if spec.has_actionable_filters():
        return spec

    spec.confidence = 0.25
    spec.notes.append("Dogrudan uygulanabilir filtre cikarilamadi.")
    return spec


def extract_date_range(
    raw_prompt: str,
    normalized_prompt: str,
    today: date,
    default_field: str | None,
) -> DateRangeFilter | None:
    range_match = DATE_RANGE_RE.search(raw_prompt)
    if range_match:
        start = parse_flexible_date(range_match.group("start"))
        end = parse_flexible_date(range_match.group("end"))
        if start and end:
            return DateRangeFilter(
                field=default_field,
                start_date=min(start, end).isoformat(),
                end_date=max(start, end).isoformat(),
            )

    month_boundary_match = re.search(
        r"(?:(?P<start_year>\d{4})\s+)?(?P<start_month>%s)\s+ayinin\s+basindan(?:\s+itibaren)?\s+(?:(?P<end_year>\d{4})\s+)?(?P<end_month>%s)\s+ayinin\s+sonuna\s+kadar"
        % ("|".join(MONTHS.keys()), "|".join(MONTHS.keys())),
        normalized_prompt,
    )
    if month_boundary_match:
        start_year = int(
            month_boundary_match.group("start_year")
            or month_boundary_match.group("end_year")
            or today.year
        )
        end_year = int(
            month_boundary_match.group("end_year")
            or month_boundary_match.group("start_year")
            or today.year
        )
        start_month = MONTHS[month_boundary_match.group("start_month")]
        end_month = MONTHS[month_boundary_match.group("end_month")]
        start_date = date(start_year, start_month, 1)
        end_day = monthrange(end_year, end_month)[1]
        end_date = date(end_year, end_month, end_day)
        if end_date < start_date:
            start_date, end_date = end_date.replace(day=1), date(start_year, start_month, monthrange(start_year, start_month)[1])
        return DateRangeFilter(
            field=default_field,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

    last_months_match = re.search(r"son\s+(\d+)\s+ay", normalized_prompt)
    if last_months_match:
        months = int(last_months_match.group(1))
        start = subtract_months(today, months)
        return DateRangeFilter(
            field=default_field,
            start_date=start.isoformat(),
            end_date=today.isoformat(),
            relative_range=f"last_{months}_months",
        )

    if "bu ay" in normalized_prompt:
        return DateRangeFilter(
            field=default_field,
            start_date=today.replace(day=1).isoformat(),
            end_date=today.isoformat(),
            relative_range="current_month",
        )

    if "gecen ay" in normalized_prompt:
        current_month_start = today.replace(day=1)
        previous_month_end = current_month_start - timedelta(days=1)
        previous_month_start = previous_month_end.replace(day=1)
        return DateRangeFilter(
            field=default_field,
            start_date=previous_month_start.isoformat(),
            end_date=previous_month_end.isoformat(),
            relative_range="previous_month",
        )

    year_span_match = re.search(
        r"(?:(?P<year>\d{4})\s+)?(?P<start>%s)\s+(?P<end>%s)\s+arasi"
        % ("|".join(MONTHS.keys()), "|".join(MONTHS.keys())),
        normalized_prompt,
    )
    if year_span_match:
        year = int(year_span_match.group("year") or today.year)
        start_month = MONTHS[year_span_match.group("start")]
        end_month = MONTHS[year_span_match.group("end")]
        start_date = date(year, min(start_month, end_month), 1)
        end_month_value = max(start_month, end_month)
        end_day = monthrange(year, end_month_value)[1]
        end_date = date(year, end_month_value, end_day)
        return DateRangeFilter(field=default_field, start_date=start_date.isoformat(), end_date=end_date.isoformat())

    single_month_match = re.search(r"(?:(?P<year>\d{4})\s+)?(?P<month>%s)\s+ayi" % "|".join(MONTHS.keys()), normalized_prompt)
    if single_month_match:
        year = int(single_month_match.group("year") or today.year)
        month = MONTHS[single_month_match.group("month")]
        start_date = date(year, month, 1)
        end_day = today.day if year == today.year and month == today.month else monthrange(year, month)[1]
        end_date = date(year, month, end_day)
        return DateRangeFilter(field=default_field, start_date=start_date.isoformat(), end_date=end_date.isoformat())

    year_match = re.search(r"(?P<year>\d{4})\s+yili", normalized_prompt)
    if year_match:
        year = int(year_match.group("year"))
        return DateRangeFilter(
            field=default_field,
            start_date=date(year, 1, 1).isoformat(),
            end_date=date(year, 12, 31).isoformat(),
        )

    return None


def extract_amount_comparison(prompt_lower: str, amount_field: str) -> AmountFilter | None:
    ge_match = re.search(
        r"(?P<amount>\d[\d\s.,]*(?:bin|milyon)?(?:\s*tl)?)\s*(?:uzeri|ustu|ve uzeri|ve ustu)",
        normalize_text_for_match(prompt_lower),
    )
    if ge_match:
        value = parse_amount_text(ge_match.group("amount"))
        if value is not None:
            return AmountFilter(field=amount_field, operator=">=", value=value)

    lt_norm = normalize_text_for_match(prompt_lower)
    lt_match = re.search(r"(?P<amount>\d[\d\s.,]*(?:bin|milyon)?(?:\s*tl)?)\s*alt", lt_norm)
    if lt_match:
        value = parse_amount_text(lt_match.group("amount"))
        if value is not None:
            if any(token in lt_norm for token in ["dahil etme", "gosterme", "haric", "dahil etme", "dahil etme"]):
                return AmountFilter(field=amount_field, operator=">=", value=value)
            return AmountFilter(field=amount_field, operator="<=", value=value)

    return None


def extract_category_filter(
    raw_prompt: str,
    normalized_prompt: str,
    report_type: str,
    normalized_schema: list[str],
) -> CategoryFilter | None:
    patterns = [
        (r"sadece\s+(?P<value>.+?)\s+departmani", "department"),
        (r"sadece\s+(?P<value>.+?)\s+bolges(?:i|indeki(?:\s+satislari)?)", "region"),
        (r"sadece\s+(?P<value>.+?)\s+carisi", "counterparty"),
        (r"sadece\s+(?P<value>.+?)\s+urunu", "product_name"),
        (r"sadece\s+(?P<value>.+?)\s+musterisi", "customer"),
    ]

    for pattern, field_name in patterns:
        match = re.search(pattern, raw_prompt, re.IGNORECASE)
        if not match:
            continue
        resolved_field = resolve_field_name(field_name, normalized_schema)
        if resolved_field is None:
            continue
        return CategoryFilter(field=resolved_field, values=[match.group("value").strip()])

    if "kdv" in normalized_prompt:
        for field_name in ["tax_type", "description", "product_name"]:
            resolved_field = resolve_field_name(field_name, normalized_schema)
            if resolved_field is not None:
                return CategoryFilter(field=resolved_field, values=["KDV"], match_mode="contains")

    defaults = get_report_filter_defaults(report_type)
    if len(defaults.get("category_fields", [])) == 1:
        only_field = resolve_field_name(defaults["category_fields"][0], normalized_schema)
        generic_match = re.search(r"sadece\s+(?P<value>.+)", raw_prompt, re.IGNORECASE)
        if only_field and generic_match:
            value = generic_match.group("value").strip()
            if value:
                return CategoryFilter(field=only_field, values=[value])
    return None


def extract_ranking_filter(normalized_prompt: str, report_type: str, defaults: dict) -> RankingSpec | None:
    count_match = TOP_N_RE.search(normalized_prompt)
    count = int(count_match.group("count")) if count_match else None
    ranking_dimensions = defaults.get("ranking_dimensions", {})

    if "en riskli cari" in normalized_prompt and "risk_score" in ranking_dimensions:
        preset = ranking_dimensions["risk_score"]
        return RankingSpec(
            scope="groups",
            group_by=list(preset["group_by"]),
            metric_field=preset["metric_field"],
            aggregate=preset["aggregate"],
            direction=preset.get("direction", "desc"),
            top_n=count or 10,
        )

    dimension_aliases = {
        "customer": ["musteri"],
        "counterparty": ["cari", "firma"],
        "department": ["departman"],
        "product_name": ["urun"],
        "salesperson": ["satis temsilcisi", "temsilci", "satici"],
        "region": ["bolge"],
        "employee_name": ["personel", "calisan"],
        "tax_type": ["vergi turu"],
        "period": ["donem"],
    }

    for dimension, aliases in dimension_aliases.items():
        if not any(alias in normalized_prompt for alias in aliases):
            continue
        if dimension not in ranking_dimensions:
            continue
        preset = ranking_dimensions[dimension]
        return RankingSpec(
            scope="groups",
            group_by=list(preset["group_by"]),
            metric_field=preset["metric_field"],
            aggregate=preset["aggregate"],
            direction=preset.get("direction", "desc"),
            top_n=count or 10,
        )

    if count is not None:
        return RankingSpec(
            scope="rows",
            metric_field=defaults.get("amount_field", "amount"),
            aggregate="sum",
            direction="desc",
            top_n=count,
        )

    return None


def parse_flexible_date(value: str) -> date | None:
    text = value.strip().replace("/", ".").replace("-", ".")
    for fmt in ("%d.%m.%Y", "%d.%m.%y"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.date()
        except ValueError:
            continue
    return None


def subtract_months(current: date, months: int) -> date:
    year = current.year
    month = current.month - months
    while month <= 0:
        year -= 1
        month += 12
    day = min(current.day, monthrange(year, month)[1])
    return date(year, month, day)


def dedupe_notes(notes: list[str]) -> list[str]:
    unique: list[str] = []
    for note in notes:
        cleaned = str(note).strip()
        if cleaned and cleaned not in unique:
            unique.append(cleaned)
    return unique
