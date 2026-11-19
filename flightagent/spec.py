"""Trip spec loading and validation. Catches bad specs before any searching."""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

IATA = re.compile(r"^[A-Z]{3}$")
REQUIRED_HARD = {
    "max_stops": int, "min_layover_min": int, "max_layover_min": int,
    "max_total_duration_min": int, "checked_bags_per_traveler": int,
    "price_cap_total": (int, float), "currency": str,
}
# Identity data belongs in agent memory, never in a shareable file.
FORBIDDEN_KEYS = re.compile(r"passport|dob|birth|card|cvv|ssn|aadhaar|pan_no|password|otp", re.I)


def load(path: str) -> dict[str, Any]:
    with open(path) as f:
        return json.load(f)


def _walk_keys(obj: Any, prefix: str = ""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield f"{prefix}{k}"
            yield from _walk_keys(v, f"{prefix}{k}.")
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v, prefix)


def check(spec: dict[str, Any]) -> list[str]:
    """Return a list of problems; empty means the spec is usable."""
    errs: list[str] = []
    for key in ("origin", "destination"):
        if not IATA.match(str(spec.get(key, ""))):
            errs.append(f"{key} must be a 3-letter IATA code")
    if spec.get("origin") == spec.get("destination"):
        errs.append("origin and destination are the same")
    t = spec.get("travelers")
    if not isinstance(t, int) or not 1 <= t <= 9:
        errs.append("travelers must be an integer from 1 to 9")

    hard = spec.get("hard", {})
    for k, typ in REQUIRED_HARD.items():
        if not isinstance(hard.get(k), typ) or isinstance(hard.get(k), bool):
            errs.append(f"hard.{k} is missing or the wrong type")
    if not errs and hard["min_layover_min"] > hard["max_layover_min"]:
        errs.append("hard.min_layover_min is greater than hard.max_layover_min")

    w = spec.get("depart_window")
    try:
        d0, d1 = (date.fromisoformat(x) for x in w)
        if d0 > d1:
            errs.append("depart_window start is after its end")
    except Exception:
        errs.append("depart_window must be [YYYY-MM-DD, YYYY-MM-DD]")

    pol = spec.get("seller_policy") or ("listed_only" if spec.get("allowed_sellers") else "airline_official")
    if pol not in ("airline_official", "listed_only"):
        errs.append("seller_policy must be airline_official or listed_only")
    allowed = spec.get("allowed_sellers") or []
    if not all(isinstance(a, str) and "." in a for a in allowed):
        errs.append("allowed_sellers must be a list of domains")
    if pol == "listed_only" and not allowed:
        errs.append("seller_policy listed_only needs at least one domain in allowed_sellers")
    for k in ("search_sources",):
        if not all(isinstance(a, str) and "." in a for a in spec.get(k) or []):
            errs.append(f"{k} must be a list of domains")
    for k in ("preferred_airlines", "avoid_airlines"):
        if not all(isinstance(a, str) and re.fullmatch(r"[A-Z0-9]{2}", a.upper()) for a in spec.get(k) or []):
            errs.append(f"{k} must be 2-character airline codes, e.g. SQ")

    drift = spec.get("max_price_drift_pct", 3)
    if not isinstance(drift, (int, float)) or not 0 <= drift <= 20:
        errs.append("max_price_drift_pct must be between 0 and 20")

    weights = spec.get("soft", {}).get("weights", {})
    if weights and abs(sum(weights.values()) - 1) > 0.01:
        errs.append("soft.weights should add up to 1")

    for k in _walk_keys(spec):
        if FORBIDDEN_KEYS.search(k.split(".")[-1]):
            errs.append(f"{k}: identity or payment data does not belong in the spec; keep it in agent memory")
    return errs
