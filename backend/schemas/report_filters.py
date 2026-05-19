from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DateRangeFilter(BaseModel):
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    relative_range: str | None = None


class AmountFilter(BaseModel):
    field: str = "amount"
    operator: Literal[">", ">=", "<", "<=", "=", "between"]
    value: float | None = None
    min_value: float | None = None
    max_value: float | None = None


class CategoryFilter(BaseModel):
    field: str
    values: list[str] = Field(default_factory=list)
    match_mode: Literal["exact", "contains", "case_insensitive"] = "case_insensitive"


class StatusFilter(BaseModel):
    field: str
    values: list[str] = Field(default_factory=list)


class SortSpec(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "desc"


class RankingSpec(BaseModel):
    scope: Literal["rows", "groups"] = "rows"
    group_by: list[str] = Field(default_factory=list)
    metric_field: str = "amount"
    aggregate: Literal["sum", "count", "mean", "max", "min", "risk_score"] = "sum"
    direction: Literal["asc", "desc"] = "desc"
    top_n: int


class ReportFilterSpec(BaseModel):
    date_range: DateRangeFilter | None = None
    amount_filters: list[AmountFilter] = Field(default_factory=list)
    category_filters: list[CategoryFilter] = Field(default_factory=list)
    status_filters: list[StatusFilter] = Field(default_factory=list)
    sort: list[SortSpec] = Field(default_factory=list)
    ranking: RankingSpec | None = None
    top_n: int | None = None
    include_only_overdue: bool = False
    include_only_unpaid: bool = False
    notes: list[str] = Field(default_factory=list)
    confidence: float = 0.0

    def has_actionable_filters(self) -> bool:
        return any(
            [
                self.date_range is not None,
                bool(self.amount_filters),
                bool(self.category_filters),
                bool(self.status_filters),
                bool(self.sort),
                self.ranking is not None,
                self.top_n is not None,
                self.include_only_overdue,
                self.include_only_unpaid,
            ]
        )


class FilterApplicationSummary(BaseModel):
    applied: bool = False
    user_prompt: str | None = None
    spec: ReportFilterSpec | None = None
    summary_lines: list[str] = Field(default_factory=list)
    input_row_count: int = 0
    filtered_row_count: int = 0
