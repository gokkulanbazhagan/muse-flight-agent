"""Where the agent may search and where it may pay.

Two lists, two jobs:
  search_sources   flight search engines (Google Flights, Skyscanner). They compare
                   every airline but never sell tickets. Search here, never pay here.
  sellers          where checkout may happen.

seller_policy:
  "airline_official" (default)  the official site of an airline that flies or sells
                                this itinerary (see airlines.REGISTRY), plus any site
                                the user listed in allowed_sellers (e.g. a travel agency)
  "listed_only"                 only the sites in allowed_sellers

Older specs without seller_policy keep their behavior: a non-empty allowed_sellers
means "listed_only".
"""
from __future__ import annotations

from typing import Any

from . import airlines
from .guard import host_of, lookalike_of, registrable, seller_allowed


def seller_policy(spec: dict[str, Any]) -> str:
    if spec.get("seller_policy"):
        return spec["seller_policy"]
    return "listed_only" if spec.get("allowed_sellers") else "airline_official"


def search_sources(spec: dict[str, Any]) -> list[str]:
    return spec.get("search_sources") or list(airlines.DEFAULT_SEARCH_SOURCES)


def is_search_source(host: str, spec: dict[str, Any]) -> bool:
    return seller_allowed(host, search_sources(spec))


def seller_verdict(seller: str, spec: dict[str, Any], carriers: set[str]) -> dict[str, Any]:
    host = host_of(seller)
    listed = spec.get("allowed_sellers") or []
    if is_search_source(host, spec) and not seller_allowed(host, listed):
        return {"seller": host, "allowed": False, "basis": None,
                "reasons": [f"{registrable(host)} is a flight search engine, not a seller; book on the airline's own site"]}
    if seller_allowed(host, listed):
        return {"seller": host, "allowed": True, "basis": "listed by the user", "reasons": []}

    policy = seller_policy(spec)
    if policy == "airline_official":
        for code in sorted(carriers):
            if seller_allowed(host, airlines.official_domains(code)):
                return {"seller": host, "allowed": True, "basis": f"official {airlines.name(code)} site", "reasons": []}
        reasons = []
        owner = next((c for c, (_, doms) in airlines.REGISTRY.items() if seller_allowed(host, doms)), None)
        if owner:
            reasons.append(f"{registrable(host)} belongs to {airlines.name(owner)}, which does not fly this itinerary")
        else:
            reasons.append(f"{registrable(host)} is not the official site of {', '.join(sorted(carriers)) or 'the airline'}; "
                           "a travel agency or other site needs to be listed by the user")
        unknown = [c for c in carriers if not airlines.official_domains(c)]
        if unknown:
            reasons.append(f"airline {', '.join(sorted(unknown))} is not in the registry; the user can list its site")
        known = [d for c in carriers for d in airlines.official_domains(c)] + listed
    else:
        reasons = ["not on allowed_sellers"]
        known = listed

    imitates = lookalike_of(host, known) if known else None
    if imitates:
        reasons.append(f"looks like an imitation of {imitates}")
    if registrable(host).count("-") >= 2:
        reasons.append("several hyphens in the domain")
    return {"seller": host, "allowed": False, "basis": None, "reasons": reasons}


def source_ok(source_url: str, seller: str, spec: dict[str, Any]) -> bool:
    """A result may come from the seller's own site or from an allowed search engine."""
    host = host_of(source_url)
    return registrable(host) == registrable(seller) or is_search_source(host, spec)
