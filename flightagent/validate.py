"""Hard-constraint filter and ranker for agent-collected flight candidates.

The LLM finds flights; this script decides which ones are allowed. Keeping the
hard-constraint check in plain code means a persuasive web page cannot talk the
agent into booking something that breaks the user's rules.

Standard library only.
"""
from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any

from . import airlines, policy
from .guard import registrable

REDEYE_START_HOUR = 23
REDEYE_END_HOUR = 5
OUTLIER_FRACTION = 0.6  # a fare below 60% of the median is suspicious


def is_redeye(depart_local: str) -> bool:
    hour = datetime.fromisoformat(depart_local).hour
    return hour >= REDEYE_START_HOUR or hour < REDEYE_END_HOUR


def total_duration(c: dict[str, Any]) -> int:
    return sum(s["duration_min"] for s in c["segments"]) + sum(c.get("layovers_min", []))


def check_hard(c: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    """Return the list of hard-constraint violations (empty means allowed)."""
    h = spec["hard"]
    reasons: list[str] = []

    carriers = airlines.carriers_of(c)
    verdict = policy.seller_verdict(c.get("seller", ""), spec, carriers)
    if not verdict["allowed"]:
        reasons.append(f"seller {c.get('seller')!r}: {'; '.join(verdict['reasons'])}")
    avoided = carriers & {a.upper() for a in spec.get("avoid_airlines", [])}
    if avoided:
        reasons.append(f"flies {', '.join(sorted(airlines.name(a) for a in avoided))}, which the user wants to avoid")

    stops = len(c["segments"]) - 1
    if stops > h["max_stops"]:
        reasons.append(f"{stops} stops > max {h['max_stops']}")

    for i, lay in enumerate(c.get("layovers_min", [])):
        if lay < h["min_layover_min"]:
            reasons.append(f"layover {i + 1} is {lay} min < min {h['min_layover_min']}")
        if lay > h["max_layover_min"]:
            reasons.append(f"layover {i + 1} is {lay} min > max {h['max_layover_min']}")

    if len(c.get("layovers_min", [])) != max(stops, 0):
        reasons.append("layover count does not match segments (data looks incomplete)")

    dur = total_duration(c)
    if dur > h["max_total_duration_min"]:
        reasons.append(f"total {dur} min > max {h['max_total_duration_min']}")

    if c.get("checked_bags_per_traveler", 0) < h["checked_bags_per_traveler"]:
        reasons.append("not enough checked bags included")

    if c.get("currency") != h["currency"]:
        reasons.append(f"currency {c.get('currency')} != {h['currency']} (convert first)")
    elif c["total_price"] > h["price_cap_total"]:
        reasons.append(f"price {c['total_price']} > cap {h['price_cap_total']}")

    if h.get("no_redeye") and is_redeye(c["segments"][0]["depart_local"]):
        reasons.append("red-eye departure")

    if h.get("seats_together") and not c.get("seats_together_available", False):
        reasons.append("adjacent seats not shown as available")

    if h.get("require_self_transfer_free") and not c.get("single_ticket", False):
        reasons.append("separate tickets (self-transfer)")

    window = spec.get("depart_window")
    if window:
        d = datetime.fromisoformat(c["segments"][0]["depart_local"]).date().isoformat()
        if not (window[0] <= d <= window[1]):
            reasons.append(f"departs {d}, outside window {window[0]}..{window[1]}")

    first, last = c["segments"][0]["from"], c["segments"][-1]["to"]
    if first != spec["origin"] or last != spec["destination"]:
        reasons.append(f"route {first}->{last} != {spec['origin']}->{spec['destination']}")

    return reasons


def normalise(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [1.0 for _ in values]
    return [(hi - v) / (hi - lo) for v in values]  # lower is better -> higher score


def layover_comfort(c: dict[str, Any], spec: dict[str, Any]) -> float:
    lays = c.get("layovers_min", [])
    if not lays:
        return 1.0
    lo, hi = spec["hard"]["min_layover_min"], spec["hard"]["max_layover_min"]
    sweet = (lo + hi) / 2
    span = (hi - lo) / 2 or 1
    return sum(max(0.0, 1 - abs(l - sweet) / span) for l in lays) / len(lays)


def score(passing: list[dict[str, Any]], spec: dict[str, Any]) -> list[dict[str, Any]]:
    w = {"duration": 0.4, "price": 0.3, "layover_comfort": 0.2, "carrier_rating": 0.1}
    w.update(spec.get("soft", {}).get("weights", {}))
    preferred = {x.upper() for x in spec.get("soft", {}).get("preferred_carriers", []) + spec.get("preferred_airlines", [])}

    dur_s = normalise([total_duration(c) for c in passing])
    price_s = normalise([c["total_price"] for c in passing])
    for c, d, p in zip(passing, dur_s, price_s):
        parts = {
            "duration": d,
            "price": p,
            "layover_comfort": layover_comfort(c, spec),
            "carrier_rating": min(c.get("carrier_rating", 3.0), 5.0) / 5.0,
        }
        total = sum(w[k] * parts[k] for k in w if k in parts)
        if airlines.carriers_of(c) & preferred:
            total += 0.03
        c["_score"] = round(total, 4)
        c["_score_parts"] = {k: round(v, 3) for k, v in parts.items()}
    return sorted(passing, key=lambda c: c["_score"], reverse=True)


def flags(c: dict[str, Any], all_prices: list[float]) -> list[str]:
    out = []
    if len(all_prices) >= 3 and c["total_price"] < OUTLIER_FRACTION * median(all_prices):
        out.append("price far below the other results: verify seller before trusting it")
    if registrable(c.get("seller", "")).count("-") >= 2:
        out.append("seller domain has several hyphens: check for a look-alike")
    return out


def fmt_minutes(m: int) -> str:
    return f"{m // 60}h{m % 60:02d}m"


def approval_card(c: dict[str, Any], spec: dict[str, Any], rank: int) -> str:
    segs = " -> ".join(
        f"{s['flight']} {s['from']} {s['depart_local'][11:16]} -> {s['to']} {s.get('arrive_local', '')[11:16]}"
        for s in c["segments"]
    )
    lays = ", ".join(fmt_minutes(l) for l in c.get("layovers_min", [])) or "nonstop"
    why = max(c["_score_parts"], key=c["_score_parts"].get).replace("_", " ")
    return (
        f"Option {rank}: {airlines.name(c['carrier'])} ({c['carrier']}), book on {c['seller']}\n"
        f"  {segs}\n"
        f"  Layovers: {lays} | Total: {fmt_minutes(total_duration(c))}\n"
        f"  {spec['travelers']} travelers, {c['checked_bags_per_traveler']} bags each, "
        f"seats together: {'yes' if c.get('seats_together_available') else 'no'}\n"
        f"  Total {c['total_price']:.2f} {c['currency']} (taxes and fees incl.)\n"
        f"  Strongest on: {why}"
    )


def run(spec: dict[str, Any], candidates: list[dict[str, Any]], top: int) -> dict[str, Any]:
    passing, rejected = [], []
    for c in candidates:
        reasons = check_hard(c, spec)
        (rejected if reasons else passing).append({**c, "_reasons": reasons} if reasons else c)

    ranked = score(passing, spec) if passing else []
    prices = [c["total_price"] for c in candidates if c.get("currency") == spec["hard"]["currency"]]
    shortlist = []
    for i, c in enumerate(ranked[:top], start=1):
        shortlist.append({
            "rank": i,
            "id": c["id"],
            "score": c["_score"],
            "score_parts": c["_score_parts"],
            "flags": flags(c, prices),
            "price_seen": c["total_price"],
            "max_price_at_checkout": round(c["total_price"] * (1 + spec.get("max_price_drift_pct", 3) / 100), 2),
            "seller": c["seller"],
            "seller_basis": policy.seller_verdict(c["seller"], spec, airlines.carriers_of(c))["basis"],
            "carriers": sorted(airlines.carriers_of(c)),
            "flights": [s["flight"] for s in c["segments"]],
            "depart_date": c["segments"][0]["depart_local"][:10],
            "approval_card": approval_card(c, spec, i),
        })
    return {
        "trip": spec.get("trip_name"),
        "checked": len(candidates),
        "passed": len(passing),
        "shortlist": shortlist,
        "rejected": [{"id": r["id"], "reasons": r["_reasons"]} for r in rejected],
        "next_step": "options ready for the user's pick" if shortlist
        else "no option passed; the rejection reasons say which rule each one broke",
    }
