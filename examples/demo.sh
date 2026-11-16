#!/usr/bin/env bash
# Full booking loop on sample data, exactly as the agent runs it (minus the browser).
set -u
cd "$(dirname "$0")/.."
RUN=runs/demo-parents-maa
rm -rf "$RUN"; mkdir -p "$RUN"
step() { printf '\n== %s ==\n' "$1"; }

step "1. Check the trip spec"
python3 -m flightagent check-spec examples/trip_spec.example.json

step "2. Scan pages before trusting them"
python3 -m flightagent scan-page examples/pages/clean_fare_page.txt --site emirates.com --run "$RUN"; echo "exit $?"
python3 -m flightagent scan-page examples/pages/injected_fare_page.txt --site cheap-fares-emirates-deals.example --run "$RUN"; echo "exit $? (2 = stop: suspected prompt injection)"

step "3. Validate and rank candidates"
python3 -m flightagent validate examples/trip_spec.example.json examples/candidates.example.json --out "$RUN/shortlist.json" --run "$RUN"

step "4. Human picks option 1"
python3 -m flightagent log "$RUN" approval --summary "user picked option 1" >/dev/null

step "5a. Pre-checkout gate: page matches approval"
python3 -m flightagent precheck examples/trip_spec.example.json "$RUN/shortlist.json" --pick 1 --live examples/live_checkout.ok.json --run "$RUN"; echo "exit $?"

step "5b. Pre-checkout gate: price jumped 6%"
python3 -m flightagent precheck examples/trip_spec.example.json "$RUN/shortlist.json" --pick 1 --live examples/live_checkout.drift.json --run "$RUN"; echo "exit $? (2 = stop and show the user)"

step "6. Fare watch (report only)"
python3 -m flightagent watch examples/watch_baseline.json examples/watch_quote.json; echo "exit $?"

step "7. Action receipt"
python3 -m flightagent receipt "$RUN"
