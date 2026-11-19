"""Collect the trip details from the user, then have the user confirm them.

Three rules keep the agent from filling in the trip on its own:

1. Every answer carries a source: "user" (the default) or "memory". Defaults are
   only used when the user said defaults are fine (--accept-defaults).
2. Nothing becomes the trip spec until the user has seen a plain-English summary
   and confirmed it (--confirm). Changing any answer clears the confirmation.
3. Output is status data, not instructions, so it cannot be mistaken for a page
   trying to steer the agent.

State lives in <run>/intake.json; the confirmed spec is <run>/trip_spec.json.
"""
from __future__ import annotations

import json
import os
from datetime import date, timedelta
from typing import Any

from . import receipt
from . import spec as spec_mod

# key, question, parser, default (None = no default)
QUESTIONS: list[tuple[str, str, str, Any]] = [
    ("origin", "Which airport are they flying from? (3-letter code, e.g. SFO)", "iata", None),
    ("destination", "Which airport are they flying to? (3-letter code, e.g. MAA)", "iata", None),
    ("depart_earliest", "Earliest departure date? (YYYY-MM-DD)", "date", None),
    ("depart_latest", "Latest departure date? (YYYY-MM-DD, same as earliest if fixed)", "date", None),
    ("travelers", "How many travelers?", "int", None),
    ("price_cap_total", "Maximum total price for everyone, taxes included?", "float", None),
    ("allowed_sellers", "Which airline websites may be used? (comma-separated domains, e.g. united.com)", "list", None),
    ("currency", "Currency for that price?", "upper", "USD"),
    ("max_stops", "Maximum stops?", "int", 1),
    ("min_layover_min", "Shortest acceptable layover, in minutes?", "int", 120),
    ("max_layover_min", "Longest acceptable layover, in minutes?", "int", 360),
    ("max_total_duration_min", "Longest total trip time, in minutes?", "int", 1800),
    ("checked_bags_per_traveler", "Checked bags per traveler?", "int", 1),
    ("no_redeye", "Avoid departures between 11 PM and 5 AM? (yes/no)", "bool", True),
    ("seats_together", "Must everyone sit together? (yes/no)", "bool", True),
    ("max_price_drift_pct", "Stop if the price rises more than what % before paying?", "float", 3),
]
REQUIRED = {"origin", "destination", "depart_earliest", "depart_latest", "travelers", "price_cap_total", "allowed_sellers"}
KINDS = {k: kind for k, _, kind, _ in QUESTIONS}
DEFAULTS = {k: d for k, _, _, d in QUESTIONS if d is not None}
SOURCES = ("user", "memory")


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


def _state_path(run: str) -> str:
    return os.path.join(run, "intake.json")


def load_state(run: str) -> dict[str, Any]:
    p = _state_path(run)
    if os.path.exists(p):
        with open(p) as f:
            return json.load(f)
    return {"answers": {}, "defaults_ok": False, "dry_run": False, "confirmed": False}


def _save(run: str, state: dict[str, Any]) -> None:
    with open(_state_path(run), "w") as f:
        json.dump(state, f, indent=2)


def _values(state: dict[str, Any]) -> dict[str, Any]:
    vals = {k: v["value"] for k, v in state["answers"].items()}
    if state["defaults_ok"]:
        for k, d in DEFAULTS.items():
            vals.setdefault(k, d)
    return vals


def build_spec(state: dict[str, Any], trip_name: str) -> dict[str, Any]:
    v = _values(state)
    a = state["answers"]
    return {
        "trip_name": trip_name,
        "mode": "dry_run" if state.get("dry_run") else "live",
        "travelers": v["travelers"],
        "traveler_profile": state.get("traveler_profile", "memory:travelers"),
        "origin": v["origin"],
        "destination": v["destination"],
        "depart_window": [v["depart_earliest"], v["depart_latest"]],
        "hard": {
            "max_stops": v["max_stops"],
            "min_layover_min": v["min_layover_min"],
            "max_layover_min": v["max_layover_min"],
            "max_total_duration_min": v["max_total_duration_min"],
            "checked_bags_per_traveler": v["checked_bags_per_traveler"],
            "price_cap_total": v["price_cap_total"],
            "currency": v["currency"],
            "no_redeye": v["no_redeye"],
            "seats_together": v["seats_together"],
            "require_self_transfer_free": True,
        },
        "soft": {"weights": {"duration": 0.4, "price": 0.3, "layover_comfort": 0.2, "carrier_rating": 0.1}},
        "services": state.get("services", []),
        "allowed_sellers": v["allowed_sellers"],
        "max_price_drift_pct": v["max_price_drift_pct"],
        "sources": {k: a[k]["source"] if k in a else "default" for k in KINDS},
    }


def summary(spec: dict[str, Any]) -> str:
    h, src = spec["hard"], spec["sources"]

    def tag(k: str) -> str:
        return {"memory": " (from memory)", "default": " (default)"}.get(src.get(k, "user"), "")

    hrs = lambda m: f"{m // 60}h{m % 60:02d}m"  # noqa: E731
    lines = [
        f"Route: {spec['origin']}{tag('origin')} to {spec['destination']}{tag('destination')}",
        f"Departing: {spec['depart_window'][0]} to {spec['depart_window'][1]}",
        f"Travelers: {spec['travelers']}{tag('travelers')}",
        f"Budget: {h['price_cap_total']:.2f} {h['currency']}{tag('currency')} total, taxes included",
        f"Airline sites: {', '.join(spec['allowed_sellers'])}",
        f"Max stops: {h['max_stops']}{tag('max_stops')}; layovers {hrs(h['min_layover_min'])} to {hrs(h['max_layover_min'])}"
        f"{tag('min_layover_min')}; max trip {hrs(h['max_total_duration_min'])}{tag('max_total_duration_min')}",
        f"Bags: {h['checked_bags_per_traveler']} checked per traveler{tag('checked_bags_per_traveler')}",
        f"Red-eyes: {'avoid' if h['no_redeye'] else 'allowed'}{tag('no_redeye')}; "
        f"seats together: {'required' if h['seats_together'] else 'not required'}{tag('seats_together')}",
        f"Price-rise stop: over {spec['max_price_drift_pct']}%{tag('max_price_drift_pct')}",
        f"Mode: {'DRY RUN (stops before payment)' if spec['mode'] == 'dry_run' else 'LIVE (books after your approval)'}",
    ]
    if spec["services"]:
        lines.append(f"Requests: {', '.join(spec['services'])}")
    return "\n".join(lines)


def intake(run: str, sets: list[str], accept_defaults: bool = False, source: str = "user",
           dry_run: bool = False, confirm: bool = False) -> dict[str, Any]:
    os.makedirs(run, exist_ok=True)
    state = load_state(run)
    spec_path = os.path.join(run, "trip_spec.json")

    if confirm and (sets or accept_defaults or dry_run):
        return {"state": "error", "errors": ["--confirm must be its own call, after the user has seen the summary"]}

    if confirm:
        if not state.get("draft"):
            return {"state": "error", "errors": ["nothing to confirm yet: the summary has not been produced"]}
        with open(spec_path, "w") as f:
            json.dump(state["draft"], f, indent=2)
        state["confirmed"] = True
        _save(run, state)
        receipt.log(run, "plan", summary="user confirmed the trip spec")
        return {"state": "confirmed", "spec": spec_path}

    if source not in SOURCES:
        return {"state": "error", "errors": [f"source must be one of {SOURCES}"]}

    errors = []
    changed = False
    for s in sets:
        if "=" not in s:
            errors.append(f"{s!r}: use key=value")
            continue
        k, raw = (x.strip() for x in s.split("=", 1))
        if k == "services":
            state["services"] = [x.strip().upper() for x in raw.split(",") if x.strip()]
            changed = True
            continue
        if k not in KINDS:
            errors.append(f"unknown field {k!r}")
            continue
        try:
            state["answers"][k] = {"value": _parse(KINDS[k], raw), "source": source}
            changed = True
        except ValueError as e:
            errors.append(f"{k}: {e}")
    if accept_defaults and not state["defaults_ok"]:
        state["defaults_ok"], changed = True, True
    if dry_run and not state["dry_run"]:
        state["dry_run"], changed = True, True

    if changed and state.get("confirmed"):
        state["confirmed"] = False
        if os.path.exists(spec_path):
            os.remove(spec_path)
    state.pop("draft", None)
    _save(run, state)

    have = set(state["answers"])
    missing_required = [k for k in KINDS if k in REQUIRED and k not in have]
    missing_optional = [] if state["defaults_ok"] else [k for k in KINDS if k not in REQUIRED and k not in have]
    questions = [{"field": k, "question": q, **({"default": d} if d is not None else {})}
                 for k, q, _, d in QUESTIONS if k in missing_required + missing_optional]
    if errors or questions:
        return {
            "state": "needs_user_answers",
            "errors": errors,
            "questions_for_user": questions,
            "note": "Answers must come from the user (or memory, marked with --source memory). "
                    "Fields with a default need the user to say the defaults are fine (--accept-defaults).",
        }

    draft = build_spec(state, os.path.basename(os.path.normpath(run)))
    problems = spec_mod.check(draft)
    today = date.today()
    if date.fromisoformat(draft["depart_window"][1]) < today:
        problems.append("depart window is in the past")
    elif date.fromisoformat(draft["depart_window"][0]) < today + timedelta(days=1):
        problems.append("earliest departure is less than a day away")
    if problems:
        return {"state": "needs_user_answers", "errors": problems, "questions_for_user": []}

    state["draft"] = draft
    _save(run, state)
    return {"state": "needs_user_confirmation", "summary_for_user": summary(draft),
            "note": "The spec is saved only after the user confirms this summary (intake --confirm)."}
