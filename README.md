# muse-flight-agent

[![tests](https://github.com/Gokkul23/muse-flight-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/Gokkul23/muse-flight-agent/actions/workflows/tests.yml)

An end-to-end flight-booking skill for personal AI agents, built for Meta's
**Muse** and portable to any agent that reads the open
[SKILL.md](https://agentskills.io) format.

I built it to book my parents' flights home from San Francisco to Chennai with
my Muse agent (Kattappa). One rule runs through it:

> **The model searches. Plain code decides. A human pays.**

## Why

A booking agent combines what Simon Willison calls the
[lethal trifecta](https://simonwillison.net/2025/Jun/16/the-lethal-trifecta/):
private data, untrusted web content, and the ability to act and pay. Muse
contains that at the platform level (isolated VM, Sentinel, surrogate
credentials, checkout approval). But the platform can't know your rules
(no red-eyes for 70-year-olds, two bags each, these five airlines only), and a
model can be talked out of them by a convincing page. So this repo puts those
rules in a small CLI the agent must run, where exit code `2` means stop.

## How it works

The agent loops on one command, `flightagent next <run>`, which reads the run
folder and says exactly what to do next:

```
INTAKE ─► SEARCH ─► VALIDATE ─► APPROVE ─► CHECKOUT ─► PRECHECK ─► PAY ─► SERVICES ─► DONE
 asks the    allowed    hard rules   user picks   live page    price/seller  platform   meals,      receipt
 user        sellers +  + ranking                 captured     /flights      approval   assistance
             scan-page                                         unchanged?    (human)
```

Every stop for the user is explicit (exit code 2). Everything else runs on its
own. The run folder is the state, so a trip survives restarts and new chats.

| Command | What it does |
| --- | --- |
| `next` | Autopilot: reads the run folder, returns the stage, the action and the exact command |
| `intake` | Asks the user for missing trip details, validates answers, writes the spec |
| `approve` | Records which option the user picked |
| `schema` | Prints the candidate format the agent must write |
| `check-spec` | Valid airports, dates, caps, weights; refuses passport/card/DOB fields in the file |
| `scan-page` | Agent-directed instructions, fake "user approved" claims, OTP/card asks, hidden CSS text, zero-width characters |
| `validate` | Stops, layover window, duration, bags, price cap, red-eyes, seats together, single ticket, route, date window, seller allowlist and look-alikes; ranks the rest and prints approval cards |
| `precheck` | Right before checkout: price drift, seller swap, flight swap, date, traveler count |
| `watch` | Report-only fare watch for a scheduled job; never rebooks |
| `log` / `receipt` | Append-only JSONL log per trip and a readable action receipt |
| `selftest` | Status check after install |

Exit codes: `0` continue · `2` stop and ask the user · `1` input error.

Architecture and the split between Muse's safety layer and this skill:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start (any machine, Python 3.10+, no dependencies)

```bash
git clone https://github.com/Gokkul23/muse-flight-agent && cd muse-flight-agent
python3 -m flightagent selftest
bash examples/demo.sh          # the guardrails on sample data
python3 -m unittest discover -s tests   # includes a full zero-to-done autopilot run
```

The demo walks one trip end to end: 2 of 6 sample itineraries pass; the
others are rejected for a 70-minute layover, a look-alike seller with a
too-cheap fare, one checked bag instead of two, and a 1:20 AM departure. An
injected page is flagged, a clean checkout passes, a 6% price jump is blocked,
and a receipt is printed.

## Run it in Muse

See [INSTALL_PROMPT.md](INSTALL_PROMPT.md): pin a commit, have Muse install the
skill's files and run its status check, store traveler details in Muse memory,
then say "book flights for my family." The agent takes it from there.

## What it will not do

It will not pay without you. Muse's checkout approval asks you to confirm the
exact amount, and no skill can switch that off; that's by design. Everything
before that tap runs on its own.

## Repo layout

```
flightagent/               CLI + modules (flow, intake, spec, guard, candidates, validate, precheck, watch, receipt, selftest)
skills/flight-booker/      SKILL.md + references (spec schema, safety checklist)
examples/                  sample spec, candidates, pages, checkout quotes, demo.sh
tests/                     35 tests, including a full autopilot run
docs/ARCHITECTURE.md       diagram, layers, known limits
```

## Privacy

No names, dates of birth, passport or card numbers belong in this repo or in a
trip spec (`check-spec` refuses them). Keep traveler details in agent memory.
`runs/` and `trip_spec.json` are git-ignored.

## Disclaimer

Personal project. Not affiliated with or endorsed by Meta. Sample fares, times
and pages are fictional. Review every booking yourself before approving payment.

MIT licensed.
