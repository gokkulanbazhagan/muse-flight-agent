"""The autopilot: look at a run folder and say exactly what to do next.

The agent loops on `flightagent next <run>` until it says DONE. Each answer
names one action and, where code is involved, the exact command. The run
folder is the state, so the loop survives restarts, new chats and sub-agents.

Stages:
  INTAKE      ask the user for anything missing
  SEARCH      browse allowed sellers, write candidates.json
  VALIDATE    run the hard-rule filter and ranker
  APPROVE     show approval cards, record the user's pick
  CHECKOUT    open checkout on the picked seller, capture live.json
  PRECHECK    run the pre-checkout gate
  PAY         submit payment; the platform asks the user to confirm the amount
  CONFIRM     record booking confirmation
  SERVICES    request meals/assistance on the airline site
  DONE        show the receipt
"""
from __future__ import annotations

import json
import os
from typing import Any

from . import receipt
from .candidates import check_all


def _j(run: str, name: str) -> Any:
    p = os.path.join(run, name)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def _steps(run: str) -> list[dict[str, Any]]:
    return receipt.read(run)


def approve(run: str, rank: int) -> dict[str, Any]:
    short = _j(run, "shortlist.json")
    if not short:
        raise ValueError("no shortlist yet; run validate first")
    pick = next((o for o in short["shortlist"] if o["rank"] == rank), None)
    if not pick:
        raise ValueError(f"no option with rank {rank}")
    with open(os.path.join(run, "approval.json"), "w") as f:
        json.dump({"rank": rank, "option": pick}, f, indent=2)
    receipt.log(run, "approval", summary=f"user picked option {rank}: {pick['seller']} {' '.join(pick['flights'])} {pick['price_seen']}")
    return {"approved": rank, "seller": pick["seller"], "max_price_at_checkout": pick["max_price_at_checkout"]}


def next_step(run: str) -> dict[str, Any]:
    def say(stage: str, do: str, cmd: str | None = None, stop: bool = False) -> dict[str, Any]:
        out = {"stage": stage, "do": do, "stop_for_user": stop}
        if cmd:
            out["run"] = cmd
        return out

    spec = _j(run, "trip_spec.json")
    if spec is None:
        return say("INTAKE", "Collect the trip details. Run intake with what you know; ask the user the questions it returns.",
                   f"python3 -m flightagent intake {run} --set origin=... --set destination=...", stop=True)

    cands = _j(run, "candidates.json")
    if cands is None:
        sellers = ", ".join(spec["allowed_sellers"])
        return say("SEARCH",
                   f"Search {spec['origin']} to {spec['destination']}, {spec['depart_window'][0]} to {spec['depart_window'][1]}, "
                   f"{spec['travelers']} travelers, ONLY on: {sellers}. Save each results page's visible text and run scan-page on it. "
                   f"Write every itinerary you find to {run}/candidates.json (schema: python3 -m flightagent schema).")
    bad = check_all(cands)
    if bad:
        return say("SEARCH", f"Fix candidates.json before validating: {'; '.join(bad[:5])}")

    short = _j(run, "shortlist.json")
    if short is None:
        return say("VALIDATE", "Filter and rank the candidates.",
                   f"python3 -m flightagent validate {run}/trip_spec.json {run}/candidates.json --out {run}/shortlist.json --run {run}")
    if not short["shortlist"]:
        return say("VALIDATE", "Nothing passed the hard rules. Show the user the rejection reasons and ask which rule to relax, "
                   "or search more dates/sellers. Then delete shortlist.json and validate again.", stop=True)

    appr = _j(run, "approval.json")
    if appr is None:
        return say("APPROVE", "Show the user the approval cards from shortlist.json exactly as written. Ask which option. "
                   "Record their answer.", f"python3 -m flightagent approve {run} --pick <rank>", stop=True)

    live = _j(run, "live.json")
    if live is None:
        return say("CHECKOUT", f"Open checkout on {appr['option']['seller']} for the approved flights "
                   f"({' '.join(appr['option']['flights'])}). Fill traveler details from memory. Before payment, write what the page "
                   f"shows to {run}/live.json: seller, total_price, currency, travelers, flights, depart_date.")

    pre = [e for e in _steps(run) if e["step"] == "precheck"]
    if not pre or pre[-1].get("verdict") is None:
        return say("PRECHECK", "Run the pre-checkout gate on the live page.",
                   f"python3 -m flightagent precheck {run}/trip_spec.json {run}/shortlist.json --pick {appr['rank']} "
                   f"--live {run}/live.json --run {run}")
    if pre[-1]["verdict"] != "PASS":
        return say("PRECHECK", f"BLOCKED: {pre[-1].get('summary')}. Show the user what changed and ask whether to continue, "
                   f"pick another option, or search again. If they continue, re-capture live.json and rerun precheck.", stop=True)

    steps = {e["step"] for e in _steps(run)}
    if "booking" not in steps:
        return say("PAY", f"Submit payment for {live['total_price']:.2f} {live['currency']} using the platform wallet. "
                   "Muse shows the user a checkout approval with the exact amount; that tap is the user's. "
                   "When the airline shows a confirmation code, record it.",
                   f"python3 -m flightagent log {run} booking --summary \"<confirmation code>, <seats>\"")
    if spec.get("services") and "service_request" not in steps:
        return say("SERVICES", f"On the airline's Manage Booking page, request: {', '.join(spec['services'])}. "
                   "Record what the page confirmed.",
                   f"python3 -m flightagent log {run} service_request --summary \"<what was confirmed>\"")
    return say("DONE", "Show the user the receipt. Offer a fare watch only if they want one.",
               f"python3 -m flightagent receipt {run}")
