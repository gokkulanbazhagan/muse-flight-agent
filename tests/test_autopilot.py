"""Walk one trip from the first question to DONE using only `next`, the way the agent does.

The two browser steps (search results, checkout page) are simulated by writing the
files the agent would write. Everything else goes through the real CLI.
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from flightagent.cli import main

EX = Path(__file__).resolve().parents[1] / "examples"


def cli(*args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main([str(a) for a in args])
    text = out.getvalue()
    try:
        return code, json.loads(text)
    except ValueError:
        return code, text


def wjson(path, obj):
    Path(path).write_text(json.dumps(obj))


def rjson(path):
    return json.loads(Path(path).read_text())


def shift(cands, days):
    """Move the sample itineraries onto future dates so the test never goes stale."""
    out = json.loads(json.dumps(cands))
    for c in out:
        for s in c["segments"]:
            for k in ("depart_local", "arrive_local"):
                if k in s:
                    d = date.fromisoformat(s[k][:10]) + timedelta(days=days)
                    s[k] = d.isoformat() + s[k][10:]
    return out


class Autopilot(unittest.TestCase):
    def test_zero_to_one(self):
        with tempfile.TemporaryDirectory() as d:
            run = os.path.join(d, "runs", "family-maa")
            start = date.today() + timedelta(days=60)
            sample = json.loads((EX / "candidates.example.json").read_text())
            offset = (start - date(2026, 11, 18)).days

            # 1. Nothing exists: the autopilot asks for intake.
            code, nxt = cli("next", run)
            self.assertEqual((code, nxt["stage"]), (2, "INTAKE"))

            # 2. The user gave only the route: intake returns the rest as questions.
            code, out = cli("intake", run, "--set", "origin=sfo", "--set", "destination=MAA")
            self.assertEqual(code, 2)
            asked = {q["field"] for q in out["ask_user"]}
            self.assertIn("travelers", asked)
            self.assertIn("price_cap_total", asked)

            # 3. A typo is caught, not silently stored.
            code, out = cli("intake", run, "--set", "travelers=two")
            self.assertTrue(out["errors"])

            # 4. The user answers everything else and accepts the defaults.
            code, out = cli("intake", run,
                            "--set", f"depart_earliest={start.isoformat()}",
                            "--set", f"depart_latest={(start + timedelta(days=4)).isoformat()}",
                            "--set", "travelers=2", "--set", "price_cap_total=3200",
                            "--set", "allowed_sellers=emirates.com, qatarairways.com, airindia.com, lufthansa.com",
                            "--set", "min_layover_min=150", "--set", "checked_bags_per_traveler=2",
                            "--set", "max_total_duration_min=1500", "--set", "services=VGML,WCHR",
                            "--accept-defaults")
            self.assertEqual(code, 0, out)
            self.assertEqual(cli("check-spec", f"{run}/trip_spec.json")[0], 0)

            # 5. Autopilot: go search.
            self.assertEqual(cli("next", run)[1]["stage"], "SEARCH")

            # 6. A malformed scrape is caught before validation.
            wjson(f"{run}/candidates.json", [{"id": "x", "seller": "emirates.com"}])
            self.assertIn("Fix candidates", cli("next", run)[1]["do"])

            # 7. The browser step writes real-looking candidates.
            wjson(f"{run}/candidates.json", shift(sample, offset))
            self.assertEqual(cli("next", run)[1]["stage"], "VALIDATE")
            code, _ = cli("validate", f"{run}/trip_spec.json", f"{run}/candidates.json", "--out", f"{run}/shortlist.json", "--run", run)
            self.assertEqual(code, 0)

            # 8. Stops for the user's pick, then records it.
            code, nxt = cli("next", run)
            self.assertEqual((code, nxt["stage"]), (2, "APPROVE"))
            self.assertEqual(cli("approve", run, "--pick", 1)[0], 0)

            # 9. Checkout: the page jumped 6% -> blocked, stops for the user.
            pick = rjson(f"{run}/approval.json")["option"]
            live = {"seller": "www." + pick["seller"], "total_price": round(pick["price_seen"] * 1.06, 2), "currency": "USD",
                    "travelers": 2, "flights": pick["flights"], "depart_date": pick["depart_date"]}
            wjson(f"{run}/live.json", live)
            self.assertEqual(cli("next", run)[1]["stage"], "PRECHECK")
            self.assertEqual(cli("precheck", f"{run}/trip_spec.json", f"{run}/shortlist.json", "--pick", 1, "--live", f"{run}/live.json", "--run", run)[0], 2)
            code, nxt = cli("next", run)
            self.assertEqual((code, nxt["stage"]), (2, "PRECHECK"))
            self.assertIn("BLOCKED", nxt["do"])

            # 10. User says the fare dropped back; recapture -> PASS -> PAY.
            live["total_price"] = pick["price_seen"]
            wjson(f"{run}/live.json", live)
            self.assertEqual(cli("precheck", f"{run}/trip_spec.json", f"{run}/shortlist.json", "--pick", 1, "--live", f"{run}/live.json", "--run", run)[0], 0)
            code, nxt = cli("next", run)
            self.assertEqual((code, nxt["stage"]), (0, "PAY"))
            self.assertIn(f"{pick['price_seen']:.2f}", nxt["do"])

            # 11. Booking confirmed -> services -> done.
            cli("log", run, "booking", "--summary", "ABC123, seats 31A 31B")
            self.assertEqual(cli("next", run)[1]["stage"], "SERVICES")
            cli("log", run, "service_request", "--summary", "VGML and WCHR confirmed")
            code, nxt = cli("next", run)
            self.assertEqual((code, nxt["stage"]), (0, "DONE"))
            code, text = cli("receipt", run)
            for word in ("approval", "precheck", "booking", "service_request"):
                self.assertIn(word, text)

    def test_nothing_passes_stops(self):
        with tempfile.TemporaryDirectory() as d:
            run = os.path.join(d, "r")
            os.makedirs(run)
            spec = json.loads((EX / "trip_spec.example.json").read_text())
            spec["hard"]["price_cap_total"] = 100
            wjson(f"{run}/trip_spec.json", spec)
            (Path(run) / "candidates.json").write_text((EX / "candidates.example.json").read_text())
            cli("validate", f"{run}/trip_spec.json", f"{run}/candidates.json", "--out", f"{run}/shortlist.json")
            code, nxt = cli("next", run)
            self.assertEqual((code, nxt["stage"]), (2, "VALIDATE"))
            self.assertIn("relax", nxt["do"])


if __name__ == "__main__":
    unittest.main()
