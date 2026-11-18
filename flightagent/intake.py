"""Build a trip spec by asking the user questions, one batch at a time.

The agent calls `flightagent intake <run>` with whatever it already knows as
`--set key=value`. The command saves the answers, and while anything required
is still missing it prints the questions to ask (exit 2). When nothing is
missing it writes runs/<run>/trip_spec.json and checks it (exit 0).

Answers are saved in runs/<run>/intake.json so the conversation can span turns.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any

from . import spec as spec_mod

# key, question, parser, default (None = must ask)
QUESTIONS: list[tuple[str, str, str, Any]] = [
    ("origin", "Which airport are they flying from? (3-letter code, e.g. SFO)", "iata", None),
    ("destination", "Which airport are they flying to? (3-letter code, e.g. MAA)", "iata", None),
    ("depart_earliest", "Earliest departure date? (YYYY-MM-DD)", "date", None),
    ("depart_latest", "Latest departure date? (YYYY-MM-DD, same as earliest if fixed)", "date", None),
    ("travelers", "How many travelers?", "int", None),
    ("price_cap_total", "Maximum total price for everyone, taxes included?", "float", None),
    ("currency", "Currency for that price? (e.g. USD)", "upper", "USD"),
    ("allowed_sellers", "Which airline websites may I book on? (comma-separated domains)", "list", None),
    ("max_stops", "Maximum stops?", "int", 1),
    ("min_layover_min", "Shortest layover you'll accept, in minutes?", "int", 120),
    ("max_layover_min", "Longest layover you'll accept, in minutes?", "int", 360),
    ("max_total_duration_min", "Longest total trip time, in minutes?", "int", 1800),
    ("checked_bags_per_traveler", "Checked bags needed per traveler?", "int", 1),
    ("no_redeye", "Avoid departures between 11 PM and 5 AM? (yes/no)", "bool", True),
    ("seats_together", "Must everyone sit together? (yes/no)", "bool", True),
    ("max_price_drift_pct", "Stop if the price rises more than what % before paying?", "float", 3),
]
ALWAYS_ASK = {"origin", "destination", "depart_earliest", "depart_latest", "travelers", "price_cap_total", "allowed_sellers"}


def _parse(kind: str, raw: str) -> Any:
    raw = raw.strip()
    if kind == "iata":
        v = raw.upper()
        if len(v) != 3 or not v.isalpha():
            raise ValueError(f"{raw!r} is not a 3-letter airport code")
        return v
    if kind == "date":
        return date.fromisoformat(raw).isoformat()
    if kind == "int":
        return int(raw)
    if kind == "float":
        return float(raw.replace(",", "").lstrip("$"))
    if kind == "upper":
        return raw.upper()
    if kind == "list":
        return [x.strip().lower() for x in raw.split(",") if x.strip()]
    if kind == "bool":
        if raw.lower() in ("yes", "y", "true", "1"):
            return True
        if raw.lower() in ("no", "n", "false", "0"):
            return False
        raise ValueError(f"{raw!r} is not yes or no")
    raise ValueError(kind)


def _path(run: str) -> str:
    return os.path.join(run, "intake.json")


def load_answers(run: str) -> dict[str, Any]:
    p = _path(run)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {}


def build_spec(a: dict[str, Any], trip_name: str) -> dict[str, Any]:
    g = lambda k: a.get(k, next(d for kk, _, _, d in QUESTIONS if kk == k))  # noqa: E731
    return {
        "trip_name": trip_name,
        "travelers": g("travelers"),
        "traveler_profile": a.get("traveler_profile", "memory:travelers"),
        "origin": g("origin"),
        "destination": g("destination"),
        "depart_window": [g("depart_earliest"), g("depart_latest")],
        "hard": {
            "max_stops": g("max_stops"),
            "min_layover_min": g("min_layover_min"),
            "max_layover_min": g("max_layover_min"),
            "max_total_duration_min": g("max_total_duration_min"),
            "checked_bags_per_traveler": g("checked_bags_per_traveler"),
            "price_cap_total": g("price_cap_total"),
            "currency": g("currency"),
            "no_redeye": g("no_redeye"),
            "seats_together": g("seats_together"),
            "require_self_transfer_free": True,
        },
        "soft": {"weights": {"duration": 0.4, "price": 0.3, "layover_comfort": 0.2, "carrier_rating": 0.1}},
        "services": a.get("services", []),
        "allowed_sellers": g("allowed_sellers"),
        "max_price_drift_pct": g("max_price_drift_pct"),
    }


def intake(run: str, sets: list[str], accept_defaults: bool = False) -> dict[str, Any]:
    os.makedirs(run, exist_ok=True)
    answers = load_answers(run)
    kinds = {k: kind for k, _, kind, _ in QUESTIONS}
    errors = []
    for s in sets:
        if "=" not in s:
            errors.append(f"{s!r}: use key=value")
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        if k == "services":
            answers[k] = [x.strip().upper() for x in v.split(",") if x.strip()]
            continue
        if k not in kinds:
            errors.append(f"unknown field {k!r}")
            continue
        try:
            answers[k] = _parse(kinds[k], v)
        except ValueError as e:
            errors.append(f"{k}: {e}")
    if accept_defaults:
        answers["_defaults_ok"] = True
    with open(_path(run), "w") as f:
        json.dump(answers, f, indent=2)

    missing = [(k, q, d) for k, q, _, d in QUESTIONS
               if k not in answers and (k in ALWAYS_ASK or not answers.get("_defaults_ok"))]
    if errors or missing:
        return {
            "done": False,
            "errors": errors,
            "ask_user": [
                {"field": k, "question": q, **({"default": d} if d is not None else {})} for k, q, d in missing
            ],
            "hint": "Ask these in one message. Fields with a default can be accepted all at once with --accept-defaults.",
        }

    trip = build_spec(answers, os.path.basename(os.path.normpath(run)))
    problems = spec_mod.check(trip)
    today = date.today()
    if date.fromisoformat(trip["depart_window"][1]) < today:
        problems.append("depart window is in the past")
    elif date.fromisoformat(trip["depart_window"][0]) < today + timedelta(days=1):
        problems.append("earliest departure is less than a day away; confirm with the user")
    out = os.path.join(run, "trip_spec.json")
    with open(out, "w") as f:
        json.dump(trip, f, indent=2)
    return {"done": not problems, "spec": out, "problems": problems,
            "ask_user": [] if not problems else [{"field": "fix", "question": p} for p in problems]}
