"""Utility helpers for loading preconfigured card templates."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List

from .schemas import PreconfiguredCardRead


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "creditcards"


@lru_cache
def load_preconfigured_cards() -> List[PreconfiguredCardRead]:
    """Return the list of preconfigured credit card templates."""

    if not DATA_DIR.exists():
        return []

    cards: List[PreconfiguredCardRead] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        cards.append(PreconfiguredCardRead.model_validate(payload))
    return cards

