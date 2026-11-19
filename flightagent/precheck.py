"""The last deterministic gate before checkout.

Run it right before the agent opens a checkout page. It compares what the user
approved with what the live page now says. Any BLOCK reason means: stop, show the
user, do not proceed. The platform's own checkout approval still follows; this is
the skill's veto, not a replacement for it.
"""
from __future__ import annotations

from typing import Any

from . import policy
from .guard import registrable


def precheck(spec: dict[str, Any], approved: dict[str, Any], live: dict[str, Any]) -> dict[str, Any]:
    """approved: the shortlist entry the user picked. live: what the checkout page shows.

    live = {"seller": "...", "total_price": 2860.0, "currency": "USD",
            "travelers": 2, "flights": ["EK226", "EK546"], "depart_date": "2026-11-19"}
    """
    block: list[str] = []
    warn: list[str] = []

    seller = policy.seller_verdict(live.get("seller", ""), spec, set(approved.get("carriers", [])))
    if not seller["allowed"]:
        block.append(f"checkout seller {seller['seller']} is not allowed: {', '.join(seller['reasons'])}")
    if registrable(live.get("seller", "")) != registrable(approved["seller"]):
        block.append(f"seller changed from {approved['seller']} to {live.get('seller')}")

    if live.get("currency") != spec["hard"]["currency"]:
        block.append(f"currency changed to {live.get('currency')}")
    else:
        cap = approved["max_price_at_checkout"]
        if live["total_price"] > cap:
            pct = (live["total_price"] / approved["price_seen"] - 1) * 100
            block.append(f"price rose {pct:.1f}% to {live['total_price']:.2f} (limit {cap:.2f})")
        if live["total_price"] > spec["hard"]["price_cap_total"]:
            block.append("price is above the trip's hard cap")
        if live["total_price"] < approved["price_seen"] * 0.9:
            warn.append("price dropped more than 10%: confirm it is the same fare and bags")

    if live.get("travelers") != spec["travelers"]:
        block.append(f"traveler count is {live.get('travelers')}, spec says {spec['travelers']}")

    want = approved.get("flights")
    if want and live.get("flights") and list(live["flights"]) != list(want):
        block.append(f"flights changed: approved {want}, page shows {live['flights']}")

    if approved.get("depart_date") and live.get("depart_date") != approved["depart_date"]:
        block.append("departure date changed")

    verdict = "BLOCK" if block else "PASS"
    return {"verdict": verdict, "block": block, "warn": warn,
            "next_step": "stop and show the user what changed" if block
            else "proceed to checkout; the platform will ask the user to approve the exact amount"}
