"""Utility helpers for loading and persisting preconfigured card templates."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, List

from .schemas import PreconfiguredCardRead, PreconfiguredCardWrite


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "creditcards"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _path_for_slug(slug: str) -> Path:
    return DATA_DIR / f"{slug}.json"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "card"


def _serialise_benefit(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = {key: value for key, value in payload.items() if value is not None}
    if cleaned.get("type") == "cumulative":
        cleaned.pop("value", None)
    return cleaned


def _serialise_card_payload(payload: PreconfiguredCardWrite, slug: str) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    benefits: Iterable[dict[str, Any]] = data.get("benefits", [])
    data["benefits"] = [_serialise_benefit(benefit) for benefit in benefits]
    data["slug"] = slug
    return data


def _ensure_unique_slug(slug: str) -> str:
    candidate = slug
    counter = 2
    while _path_for_slug(candidate).exists():
        candidate = f"{slug}-{counter}"
        counter += 1
    return candidate


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


def load_preconfigured_card(slug: str) -> PreconfiguredCardRead:
    """Load a single preconfigured card template by slug."""

    path = _path_for_slug(slug)
    if not path.exists():
        raise FileNotFoundError(slug)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return PreconfiguredCardRead.model_validate(payload)


def create_preconfigured_card(payload: PreconfiguredCardWrite) -> PreconfiguredCardRead:
    """Persist a new preconfigured card template to disk."""

    desired_slug = _slugify(payload.slug or payload.card_type)
    slug = _ensure_unique_slug(desired_slug)
    card_payload = _serialise_card_payload(payload, slug)
    path = _path_for_slug(slug)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(card_payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    load_preconfigured_cards.cache_clear()
    return PreconfiguredCardRead.model_validate(card_payload)


def update_preconfigured_card(
    slug: str, payload: PreconfiguredCardWrite
) -> PreconfiguredCardRead:
    """Update an existing template, optionally renaming its slug."""

    original_path = _path_for_slug(slug)
    if not original_path.exists():
        raise FileNotFoundError(slug)

    desired_slug = payload.slug or slug
    new_slug = _slugify(desired_slug)
    if new_slug != slug and _path_for_slug(new_slug).exists():
        raise FileExistsError(new_slug)

    card_payload = _serialise_card_payload(payload, new_slug)
    new_path = _path_for_slug(new_slug)
    with new_path.open("w", encoding="utf-8") as handle:
        json.dump(card_payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    if new_slug != slug:
        original_path.unlink(missing_ok=True)

    load_preconfigured_cards.cache_clear()
    return PreconfiguredCardRead.model_validate(card_payload)


def delete_preconfigured_card(slug: str) -> None:
    """Remove a preconfigured card template from disk."""

    path = _path_for_slug(slug)
    if not path.exists():
        raise FileNotFoundError(slug)
    path.unlink()
    load_preconfigured_cards.cache_clear()

