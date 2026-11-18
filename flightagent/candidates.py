"""Shape checks for agent-written candidates, so a bad scrape fails loudly, not as a crash."""
from __future__ import annotations

from datetime import datetime
from typing import Any

SCHEMA = {
    "id": "string, unique",
    "seller": "domain you would check out on, e.g. singaporeair.com",
    "carrier": "airline code, e.g. SQ",
    "total_price": "number, all travelers, taxes and fees included",
    "currency": "e.g. USD",
    "checked_bags_per_traveler": "integer",
    "seats_together_available": "true/false",
    "single_ticket": "true/false",
    "carrier_rating": "optional number 0-5",
    "segments": "list of {flight, from, to, depart_local 'YYYY-MM-DDTHH:MM', arrive_local, duration_min}",
    "layovers_min": "list of minutes, one per connection",
}


def check_one(c: Any) -> list[str]:
    if not isinstance(c, dict):
        return ["candidate is not an object"]
    cid = c.get("id", "?")
    errs = []
    for k in ("id", "seller", "carrier", "total_price", "currency", "segments"):
        if k not in c:
            errs.append(f"{cid}: missing {k}")
    if errs:
        return errs
    if not isinstance(c["total_price"], (int, float)) or c["total_price"] <= 0:
        errs.append(f"{cid}: total_price must be a positive number")
    segs = c["segments"]
    if not isinstance(segs, list) or not segs:
        return errs + [f"{cid}: segments must be a non-empty list"]
    for i, s in enumerate(segs):
        for k in ("flight", "from", "to", "depart_local", "duration_min"):
            if k not in s:
                errs.append(f"{cid}: segment {i + 1} missing {k}")
        try:
            datetime.fromisoformat(s.get("depart_local", ""))
        except ValueError:
            errs.append(f"{cid}: segment {i + 1} depart_local is not YYYY-MM-DDTHH:MM")
    for i in range(len(segs) - 1):
        if segs[i].get("to") != segs[i + 1].get("from"):
            errs.append(f"{cid}: segment {i + 1} lands at {segs[i].get('to')} but segment {i + 2} leaves {segs[i + 1].get('from')}")
    return errs


def check_all(cands: Any) -> list[str]:
    if not isinstance(cands, list) or not cands:
        return ["candidates.json must be a non-empty list"]
    errs = [e for c in cands for e in check_one(c)]
    ids = [c.get("id") for c in cands if isinstance(c, dict)]
    if len(ids) != len(set(ids)):
        errs.append("candidate ids must be unique")
    return errs
