"""Append-only run log (JSONL) and a human-readable action receipt.

Every step the agent takes is one line in runs/<run_id>/log.jsonl. At the end,
`receipt` turns it into a short Markdown summary the user can read: what was
opened, what was rejected and why, what was approved, what was paid.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

STEPS = ("plan", "search", "page_scan", "validate", "approval", "precheck", "checkout", "booking", "service_request", "watch", "note")


def log(run_dir: str, step: str, **data: Any) -> dict[str, Any]:
    if step not in STEPS:
        raise ValueError(f"unknown step {step!r}; use one of {', '.join(STEPS)}")
    os.makedirs(run_dir, exist_ok=True)
    entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "step": step, **data}
    with open(os.path.join(run_dir, "log.jsonl"), "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read(run_dir: str) -> list[dict[str, Any]]:
    path = os.path.join(run_dir, "log.jsonl")
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def receipt(run_dir: str) -> str:
    entries = read(run_dir)
    if not entries:
        return "# Action receipt\n\nNo steps logged yet.\n"
    lines = [f"# Action receipt: {os.path.basename(os.path.normpath(run_dir))}", ""]
    sites = sorted({e.get("site") for e in entries if e.get("site")})
    if sites:
        lines += [f"**Sites opened:** {', '.join(sites)}", ""]
    flagged = [e for e in entries if e["step"] == "page_scan" and e.get("suspicious")]
    if flagged:
        lines += [f"**Suspected prompt injections:** {len(flagged)} (not followed)", ""]
    lines += ["| Time (UTC) | Step | Detail |", "| --- | --- | --- |"]
    for e in entries:
        detail = e.get("summary") or ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("ts", "step"))
        lines.append(f"| {e['ts'][11:19]} | {e['step']} | {str(detail)[:120]} |")
    return "\n".join(lines) + "\n"
