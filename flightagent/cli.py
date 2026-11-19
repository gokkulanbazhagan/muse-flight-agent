"""Command line the agent calls at each step. Every command prints JSON or text
and exits non-zero when the agent must stop and ask the user.

  python3 -m flightagent next        runs/<id>          # autopilot: which stage the trip is in
  python3 -m flightagent intake      runs/<id> --set origin=SFO ... [--source memory] [--accept-defaults] [--dry-run]
  python3 -m flightagent intake      runs/<id> --confirm # only after the user confirmed the summary
  python3 -m flightagent approve     runs/<id> --pick 1 --user-said "option 1 please"
  python3 -m flightagent schema
  python3 -m flightagent check-spec  trip_spec.json
  python3 -m flightagent scan-page   page.txt           [--run runs/<id>] [--site airline.com]
  python3 -m flightagent validate    trip_spec.json candidates.json [--out shortlist.json] [--run ...]
  python3 -m flightagent precheck    trip_spec.json shortlist.json --pick 1 --live live.json [--run ...]
  python3 -m flightagent watch       baseline.json quote.json [--threshold 3]
  python3 -m flightagent log         runs/<id> <step> --summary "..."
  python3 -m flightagent receipt     runs/<id>
  python3 -m flightagent selftest

Exit codes: 0 ok, 2 needs the user (or blocked), 1 usage or input error.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__, flow, guard, intake, precheck, receipt, spec, validate, watch
from .candidates import SCHEMA, check_all


def _load(path: str):
    with open(path) as f:
        return json.load(f)


def _dump(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def cmd_check_spec(a) -> int:
    errs = spec.check(_load(a.spec))
    _dump({"ok": not errs, "problems": errs})
    return 0 if not errs else 2


def cmd_scan_page(a) -> int:
    with open(a.file, encoding="utf-8", errors="replace") as f:
        result = guard.scan_text(f.read())
    if a.run:
        receipt.log(a.run, "page_scan", site=a.site, suspicious=result["suspicious"],
                    summary=f"{a.site or a.file}: {len(result['hits'])} suspicious pattern(s)")
    _dump(result)
    return 2 if result["suspicious"] else 0


def cmd_validate(a) -> int:
    s = _load(a.spec)
    errs = spec.check(s)
    if errs:
        _dump({"ok": False, "problems": errs})
        return 2
    cands = _load(a.candidates)
    bad = check_all(cands, s)
    if bad:
        _dump({"ok": False, "problems": bad})
        return 2
    result = validate.run(s, cands, a.top)
    if a.out:
        with open(a.out, "w") as f:
            json.dump(result, f, indent=2)
    if a.run:
        receipt.log(a.run, "validate", summary=f"{result['passed']}/{result['checked']} passed; "
                    f"rejected: {', '.join(r['id'] for r in result['rejected']) or 'none'}")
    for opt in result["shortlist"]:
        print(opt["approval_card"], end="\n\n")
    for r in result["rejected"]:
        print(f"rejected {r['id']}: {'; '.join(r['reasons'])}", file=sys.stderr)
    print(f"{result['passed']}/{result['checked']} passed. Status: {result['next_step']}")
    return 0 if result["shortlist"] else 2


def cmd_precheck(a) -> int:
    s = _load(a.spec)
    shortlist = _load(a.shortlist)["shortlist"]
    picked = next((o for o in shortlist if o["rank"] == a.pick), None)
    if not picked:
        print(f"no option with rank {a.pick} in the shortlist", file=sys.stderr)
        return 1
    result = precheck.precheck(s, picked, _load(a.live))
    if a.run:
        receipt.log(a.run, "precheck", verdict=result["verdict"], live_sha=flow.file_sha(a.live), summary=f"{result['verdict']}: {'; '.join(result['block']) or 'all checks passed'}")
    _dump(result)
    return 0 if result["verdict"] == "PASS" else 2


def cmd_intake(a) -> int:
    result = intake.intake(a.run, a.set or [], a.accept_defaults, a.source, a.dry_run, a.confirm)
    _dump(result)
    if result["state"] == "error":
        return 1
    return 0 if result["state"] == "confirmed" else 2


def cmd_next(a) -> int:
    result = flow.next_step(a.run)
    _dump(result)
    return 2 if result["needs_user"] else 0


def cmd_approve(a) -> int:
    _dump(flow.approve(a.run, a.pick, a.user_said))
    return 0


def cmd_schema(_a) -> int:
    _dump(SCHEMA)
    return 0


def cmd_watch(a) -> int:
    result = watch.compare(_load(a.baseline), _load(a.quote), a.threshold)
    _dump(result)
    return 2 if result["notify"] else 0


def cmd_log(a) -> int:
    _dump(receipt.log(a.run, a.step, summary=a.summary))
    return 0


def cmd_receipt(a) -> int:
    print(receipt.receipt(a.run), end="")
    return 0


def cmd_selftest(_a) -> int:
    from .selftest import run as selftest_run
    ok, report = selftest_run()
    print(report)
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="flightagent", description="Deterministic guardrails for an agentic flight booker.")
    ap.add_argument("--version", action="version", version=f"flightagent {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("check-spec"); p.add_argument("spec"); p.set_defaults(fn=cmd_check_spec)
    p = sub.add_parser("scan-page"); p.add_argument("file"); p.add_argument("--run"); p.add_argument("--site")
    p.set_defaults(fn=cmd_scan_page)
    p = sub.add_parser("validate"); p.add_argument("spec"); p.add_argument("candidates")
    p.add_argument("--out"); p.add_argument("--top", type=int, default=3); p.add_argument("--run")
    p.set_defaults(fn=cmd_validate)
    p = sub.add_parser("precheck"); p.add_argument("spec"); p.add_argument("shortlist")
    p.add_argument("--pick", type=int, required=True); p.add_argument("--live", required=True); p.add_argument("--run")
    p.set_defaults(fn=cmd_precheck)
    p = sub.add_parser("intake"); p.add_argument("run"); p.add_argument("--set", action="append")
    p.add_argument("--source", default="user", choices=intake.SOURCES)
    p.add_argument("--accept-defaults", action="store_true"); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm", action="store_true"); p.set_defaults(fn=cmd_intake)
    p = sub.add_parser("next"); p.add_argument("run"); p.set_defaults(fn=cmd_next)
    p = sub.add_parser("approve"); p.add_argument("run"); p.add_argument("--pick", type=int, required=True)
    p.add_argument("--user-said", required=True); p.set_defaults(fn=cmd_approve)
    p = sub.add_parser("schema"); p.set_defaults(fn=cmd_schema)
    p = sub.add_parser("watch"); p.add_argument("baseline"); p.add_argument("quote")
    p.add_argument("--threshold", type=float, default=3.0); p.set_defaults(fn=cmd_watch)
    p = sub.add_parser("log"); p.add_argument("run"); p.add_argument("step", choices=receipt.STEPS)
    p.add_argument("--summary", required=True); p.set_defaults(fn=cmd_log)
    p = sub.add_parser("receipt"); p.add_argument("run"); p.set_defaults(fn=cmd_receipt)
    p = sub.add_parser("selftest"); p.set_defaults(fn=cmd_selftest)

    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (OSError, ValueError, KeyError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
