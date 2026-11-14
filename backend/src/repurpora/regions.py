"""Canonical regions, so any geography a user names maps onto one consistent profile.

Multipliers scale the India-baseline synthetic market tables. Values are illustrative and documented as
synthetic: market ≈ relative pharma spend, patients ≈ relative population exposure, competition ≈ relative generic density.
"""

from __future__ import annotations

import re

REGIONS: dict[str, dict[str, float | str]] = {
    "India": {"market": 1.0, "patients": 1.0, "competition": 1.0, "currency": "USD"},
    "US": {"market": 6.5, "patients": 0.28, "competition": 0.6, "currency": "USD"},
    "EU": {"market": 3.9, "patients": 0.36, "competition": 0.7, "currency": "USD"},
    "UK": {"market": 0.9, "patients": 0.05, "competition": 0.6, "currency": "USD"},
    "China": {"market": 3.4, "patients": 1.0, "competition": 1.1, "currency": "USD"},
    "Japan": {"market": 1.6, "patients": 0.09, "competition": 0.5, "currency": "USD"},
    "Brazil": {"market": 0.8, "patients": 0.15, "competition": 0.9, "currency": "USD"},
    "Africa": {"market": 0.5, "patients": 1.0, "competition": 0.7, "currency": "USD"},
    "Southeast Asia": {"market": 0.7, "patients": 0.48, "competition": 0.9, "currency": "USD"},
    "Middle East": {"market": 0.6, "patients": 0.3, "competition": 0.6, "currency": "USD"},
    "Global": {"market": 20.0, "patients": 5.6, "competition": 1.6, "currency": "USD"},
}

_ALIASES = {
    "India": r"india|indian|bharat",
    "US": r"\bus\b|\busa\b|u\.s\.|united states|america|american",
    "EU": r"\beu\b|europe|european|germany|france|italy|spain|netherlands",
    "UK": r"\buk\b|united kingdom|britain|england",
    "China": r"china|chinese",
    "Japan": r"japan|japanese",
    "Brazil": r"brazil|latam|latin america",
    "Africa": r"africa|nigeria|kenya|south africa",
    "Southeast Asia": r"southeast asia|south-east asia|asean|indonesia|vietnam|thailand|philippines",
    "Middle East": r"middle east|gcc|saudi|uae|emirates",
    "Global": r"global|worldwide|world-wide|international",
}
_ALIAS_RE = {k: re.compile(v, re.I) for k, v in _ALIASES.items()}


def detect(text: str) -> str | None:
    """Region explicitly named in free text, or None."""
    for name, rx in _ALIAS_RE.items():
        if rx.search(text or ""):
            return name
    return None


def canonical(name: str | None, default: str = "India") -> str:
    if not name:
        return default
    for k in REGIONS:
        if k.lower() == name.strip().lower():
            return k
    return detect(name) or default


def profile(name: str | None) -> dict:
    return REGIONS[canonical(name)]
