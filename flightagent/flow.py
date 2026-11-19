"""Autopilot status: read a run folder and report which stage the trip is in.

`flightagent next <run>` returns plain status data:

  stage        INTAKE, CONFIRM, SEARCH, VALIDATE, APPROVE, CHECKOUT, PRECHECK,
               PAY, DRY_RUN_COMPLETE, CONFIRMATION, SERVICES or DONE
  status       one sentence describing the current state
  missing      what is not there yet
  needs_user   true when the next input can only come from the user
  command      the flightagent command for this stage, when there is one

What to do at each stage is defined in SKILL.md, not in this output. Keeping tool
output descriptive (no instructions) means it can never look like a page trying
to steer the agent, and the playbook stays in one trusted place.
"""
from __future__ import annotations

import json
import os
from typing import Any

from . import receipt
from .candidates import check_all
from .guard import registrable

ORDINALS = {1: ("1", "one", "first"), 2: ("2", "two", "second"), 3: ("3", "three", "third"),
            4: ("4", "four", "fourth"), 5: ("5", "five", "fifth")}


def _j(run: str, name: str) -> Any:
    p = os.path.join(run, name)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def approve(run: str, rank: int, user_said: str) -> dict[str, Any]:
    """Record the user's pick. `user_said` is the user's reply, quoted as they wrote it."""
    short = _j(run, "shortlist.json")
    if not short:
        raise ValueError("no shortlist yet")
    pick = next((o for o in short["shortlist"] if o["rank"] == rank), None)
    if not pick:
        raise ValueError(f"no option with rank {rank}")
    words = user_said.lower().replace(",", " ").replace(".", " ").split()
    if not user_said.strip() or not any(w in words for w in ORDINALS.get(rank, (str(rank),))):
        raise ValueError(f"the user's reply does not mention option {rank}; quote the user's actual reply with --user-said")
    with open(os.path.join(run, "approval.json"), "w") as f:
        json.dump({"rank": rank, "option": pick, "user_said": user_said}, f, indent=2)
    receipt.log(run, "approval", summary=f"user picked option {rank} ('{user_said[:60]}'): "
                f"{pick['seller']} {' '.join(pick['flights'])} {pick['price_seen']}")
    return {"approved": rank, "seller": pick["seller"], "max_price_at_checkout": pick["max_price_at_checkout"]}


def _status(stage: str, status: str, missing: list[str] | None = None, needs_user: bool = False,
            command: str | None = None, **extra: Any) -> dict[str, Any]:
    out = {"stage": stage, "status": status, "missing": missing or [], "needs_user": needs_user}
    if command:
        out["command"] = command
    out.update(extra)
    return out


def next_step(run: str) -> dict[str, Any]:
    log = receipt.read(run)
    spec = _j(run, "trip_spec.json")
    if spec is None:
        state = _j(run, "intake.json") or {}
        if state.get("draft"):
            return _status("CONFIRM", "Trip summary produced; the user has not confirmed it.",
                           ["user confirmation"], True, f"python3 -m flightagent intake {run} --confirm")
        return _status("INTAKE", "No confirmed trip details yet.", ["trip details from the user"], True,
                       f"python3 -m flightagent intake {run} --set key=value ...")

    cands = _j(run, "candidates.json")
    scanned = {registrable(e["site"]) for e in log if e["step"] == "page_scan" and e.get("site")}
    if cands is None:
        return _status("SEARCH", f"No search results recorded. Allowed sites: {', '.join(spec['allowed_sellers'])}.",
                       ["candidates.json", *(f"page scan for {s}" for s in spec["allowed_sellers"] if registrable(s) not in scanned)],
                       command="python3 -m flightagent scan-page <page.txt> --site <domain> --run " + run,
                       window=spec["depart_window"], route=f"{spec['origin']}-{spec['destination']}", travelers=spec["travelers"])
    bad = check_all(cands)
    unscanned = sorted({registrable(c["seller"]) for c in cands if isinstance(c, dict) and c.get("seller")} - scanned)
    if unscanned:
        bad.append(f"no page scan logged for {', '.join(unscanned)}: candidates must come from scanned live pages")
    if bad:
        return _status("SEARCH", "Search results are recorded but not usable yet.", bad[:6])

    short = _j(run, "shortlist.json")
    if short is None:
        return _status("VALIDATE", "Search results are ready to be checked against the trip rules.", ["shortlist.json"],
                       command=f"python3 -m flightagent validate {run}/trip_spec.json {run}/candidates.json "
                               f"--out {run}/shortlist.json --run {run}")
    if not short["shortlist"]:
        return _status("VALIDATE", "No option passed the trip rules.", ["an option that passes"], True,
                       rejected=short["rejected"])

    appr = _j(run, "approval.json")
    if appr is None:
        return _status("APPROVE", f"{len(short['shortlist'])} option(s) passed; the user has not picked one.",
                       ["user's pick"], True, f"python3 -m flightagent approve {run} --pick <rank> --user-said \"<user's reply>\"",
                       approval_cards=[o["approval_card"] for o in short["shortlist"]])

    opt = appr["option"]
    live = _j(run, "live.json")
    if live is None:
        return _status("CHECKOUT", f"Option {appr['rank']} approved ({opt['seller']}, {' '.join(opt['flights'])}); "
                       "checkout page values not captured yet.", ["live.json"])

    pre = [e for e in log if e["step"] == "precheck"]
    if not pre or pre[-1].get("live_sha") != file_sha(os.path.join(run, "live.json")):
        return _status("PRECHECK", "Checkout values captured; pre-checkout gate has not run on them.", ["precheck result"],
                       command=f"python3 -m flightagent precheck {run}/trip_spec.json {run}/shortlist.json "
                               f"--pick {appr['rank']} --live {run}/live.json --run {run}")
    if pre[-1].get("verdict") != "PASS":
        return _status("PRECHECK", f"Pre-checkout gate blocked: {pre[-1].get('summary')}", ["user decision"], True)

    if spec.get("mode") == "dry_run":
        return _status("DRY_RUN_COMPLETE", f"Dry run complete. Gate passed at {live['total_price']:.2f} {live['currency']}; "
                       "payment is not part of a dry run.", [], True, f"python3 -m flightagent receipt {run}")

    steps = {e["step"] for e in log}
    if "booking" not in steps:
        return _status("PAY", f"Gate passed at {live['total_price']:.2f} {live['currency']}; no booking confirmation recorded.",
                       ["platform payment approval by the user", "confirmation code"],
                       command=f"python3 -m flightagent log {run} booking --summary \"<confirmation code>\"")
    if spec.get("services") and "service_request" not in steps:
        return _status("SERVICES", f"Booked. Requests not yet recorded: {', '.join(spec['services'])}.",
                       ["service request result"],
                       command=f"python3 -m flightagent log {run} service_request --summary \"<result>\"")
    return _status("DONE", "Trip booked and recorded.", [], command=f"python3 -m flightagent receipt {run}")


def file_sha(path: str) -> str:
    import hashlib
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]
