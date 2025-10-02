"""Shared constants and helpers for backend test suites."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.models import BenefitFrequency, BenefitType  # noqa: E402


FROZEN_TODAY = date(2024, 5, 20)
FEE_DUE_DATE = date(2024, 8, 15)
FREQUENCIES: tuple[BenefitFrequency, ...] = (
    BenefitFrequency.monthly,
    BenefitFrequency.quarterly,
    BenefitFrequency.semiannual,
    BenefitFrequency.yearly,
)
TYPE_VALUES = {
    BenefitType.standard: 120.0,
    BenefitType.incremental: 150.0,
    BenefitType.cumulative: 0.0,
}
WINDOW_COUNT_BY_FREQUENCY = {
    BenefitFrequency.monthly.value: 12,
    BenefitFrequency.quarterly.value: 4,
    BenefitFrequency.semiannual.value: 2,
    BenefitFrequency.yearly.value: 1,
}

