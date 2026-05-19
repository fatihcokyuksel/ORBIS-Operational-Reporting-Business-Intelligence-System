from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal
from functools import lru_cache
import os

from dotenv import load_dotenv


load_dotenv()


def _read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "hayir", "hayır"}


def _read_decimal(name: str, default: str) -> Decimal:
    value = os.getenv(name)
    if value is None or not value.strip():
        return Decimal(default)
    return Decimal(value.strip())


@dataclass(frozen=True)
class Settings:
    GOOGLE_API_KEY: str | None
    DEFAULT_TIMEZONE: str
    DEFAULT_CURRENCY: str
    CURRENCY_CONVERSION_STRATEGY: str
    EMPLOYER_SGK_RATE: Decimal
    WARNING_MISMATCH_TOLERANCE: Decimal
    STRICT_INVENTORY_VALIDATION: bool
    DEFAULT_COST_METHOD: str
    MASK_SENSITIVE_DEBUG: bool
    MASK_SENSITIVE_EXPORTS: bool
    REPORT_VERSION: str
    CALCULATION_VERSION: str
    REPORT_AI_ANALYSIS_ENABLED: bool

    def public_snapshot(self) -> dict:
        snapshot = asdict(self)
        snapshot.pop("GOOGLE_API_KEY", None)
        return snapshot


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        GOOGLE_API_KEY=os.getenv("GOOGLE_API_KEY"),
        DEFAULT_TIMEZONE=os.getenv("DEFAULT_TIMEZONE", "Europe/Istanbul").strip() or "Europe/Istanbul",
        DEFAULT_CURRENCY=os.getenv("DEFAULT_CURRENCY", "TRY").strip().upper() or "TRY",
        CURRENCY_CONVERSION_STRATEGY=os.getenv(
            "CURRENCY_CONVERSION_STRATEGY",
            "none_warn_and_partition",
        ).strip()
        or "none_warn_and_partition",
        EMPLOYER_SGK_RATE=_read_decimal("EMPLOYER_SGK_RATE", "0.225"),
        WARNING_MISMATCH_TOLERANCE=_read_decimal("WARNING_MISMATCH_TOLERANCE", "1.00"),
        STRICT_INVENTORY_VALIDATION=_read_bool("STRICT_INVENTORY_VALIDATION", False),
        DEFAULT_COST_METHOD=os.getenv("DEFAULT_COST_METHOD", "weighted_average").strip() or "weighted_average",
        MASK_SENSITIVE_DEBUG=_read_bool("MASK_SENSITIVE_DEBUG", True),
        MASK_SENSITIVE_EXPORTS=_read_bool("MASK_SENSITIVE_EXPORTS", False),
        REPORT_VERSION=os.getenv("REPORT_VERSION", "2.1.0").strip() or "2.1.0",
        CALCULATION_VERSION=os.getenv("CALCULATION_VERSION", "1.3.0").strip() or "1.3.0",
        REPORT_AI_ANALYSIS_ENABLED=_read_bool("REPORT_AI_ANALYSIS_ENABLED", True),
    )


settings = get_settings()
GOOGLE_API_KEY = settings.GOOGLE_API_KEY
