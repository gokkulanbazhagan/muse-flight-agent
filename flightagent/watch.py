"""Report-only fare watch. Compares today's quote with the approved baseline.

Designed for a scheduled job in the agent's VM. It never books, cancels or
rebooks; it only decides whether the user should hear about a change.
"""
from __future__ import annotations

from typing import Any


def compare(baseline: dict[str, Any], quote: dict[str, Any], threshold_pct: float = 3.0) -> dict[str, Any]:
    if baseline.get("currency") != quote.get("currency"):
        return {"notify": True, "message": "Quote currency changed; check manually.", "change_pct": None}
    if not quote.get("available", True):
        return {"notify": True, "message": "The watched fare is no longer listed.", "change_pct": None}
    old, new = float(baseline["total_price"]), float(quote["total_price"])
    pct = (new - old) / old * 100
    notify = abs(pct) >= threshold_pct
    direction = "dropped" if pct < 0 else "rose"
    msg = (f"Fare {direction} {abs(pct):.1f}%: {old:.2f} -> {new:.2f} {quote['currency']}. "
           "Nothing was changed; reply if you want me to look at rebooking options.") if notify else \
          f"No meaningful change ({pct:+.1f}%)."
    return {"notify": notify, "message": msg, "change_pct": round(pct, 2)}
