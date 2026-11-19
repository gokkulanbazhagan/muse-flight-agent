"""Walk one trip from the first question to DONE using `next`, the way the agent does,
and check the agent cannot skip the user at intake or at the pick.

The two browser steps (results pages, checkout page) are simulated by writing the
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


def answer_everything(run, start, *extra):
    return cli("intake", run,
               "--set", f"depart_earliest={start.isoformat()}",
               "--set", f"depart_latest={(start + timedelta(days=4)).isoformat()}",
               "--set", "travelers=2", "--set", "price_cap_total=3200",
               "--set", "traveler_profile=family",
               "--set", "min_layover_min=150", "--set", "checked_bags_per_traveler=2",
               "--set", "max_total_duration_min=1500", "--set", "services=VGML,WCHR",
               "--accept-defaults", *extra)


def scan_all(run):
    for site in ("emirates.com", "google.com", "lufthansa.com", "airindia.com", "cheap-fares-emirates-deals.example"):
        page = EX / "pages" / ("injected_fare_page.txt" if site.endswith(".example") else "clean_fare_page.txt")
        cli("scan-page", page, "--site", site, "--run", run)


class Autopilot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.run = os.path.join(self.tmp.name, "runs", "family-maa")
        self.start = date.today() + timedelta(days=60)
        self.offset = (self.start - date(2026, 11, 18)).days

    def tearDown(self):
        self.tmp.cleanup()

    def test_zero_to_one(self):
        run = self.run
        # Nothing yet: the user has to supply the trip.
        code, nxt = cli("next", run)
        self.assertEqual((code, nxt["stage"], nxt["needs_user"]), (2, "INTAKE", True))

        # Route only: the rest come back as questions, defaults included.
        code, out = cli("intake", run, "--set", "origin=sfo", "--set", "destination=MAA")
        self.assertEqual((code, out["state"]), (2, "needs_user_answers"))
        asked = {q["field"] for q in out["questions_for_user"]}
        self.assertTrue({"travelers", "price_cap_total", "depart_earliest", "max_stops"} <= asked)

        # A typo is caught, not stored.
        code, out = cli("intake", run, "--set", "travelers=two")
        self.assertTrue(out["errors"])

        # All answered: a summary for the user, but no spec yet.
        code, out = answer_everything(run, self.start)
        self.assertEqual(out["state"], "needs_user_confirmation", out)
        self.assertIn("SFO to MAA", out["summary_for_user"])
        self.assertIn("(default)", out["summary_for_user"])
        self.assertFalse(os.path.exists(f"{run}/trip_spec.json"))
        self.assertEqual(cli("next", run)[1]["stage"], "CONFIRM")

        # Confirm must be its own call.
        self.assertEqual(cli("intake", run, "--set", "travelers=3", "--confirm")[0], 1)
        code, out = cli("intake", run, "--confirm")
        self.assertEqual((code, out["state"]), (0, "confirmed"))
        self.assertEqual(cli("check-spec", f"{run}/trip_spec.json")[0], 0)

        # Search: invented results without source pages or scans are refused.
        self.assertEqual(cli("next", run)[1]["stage"], "SEARCH")
        made_up = shift(json.loads((EX / "candidates.example.json").read_text()), self.offset)
        for c in made_up:
            c.pop("source_url")
        wjson(f"{run}/candidates.json", made_up)
        self.assertTrue(any("source_url" in m for m in cli("next", run)[1]["missing"]))

        # Real-looking results but no page scans logged: still refused.
        wjson(f"{run}/candidates.json", shift(json.loads((EX / "candidates.example.json").read_text()), self.offset))
        self.assertTrue(any("no page scan" in m for m in cli("next", run)[1]["missing"]))

        scan_all(run)
        self.assertEqual(cli("next", run)[1]["stage"], "VALIDATE")
        code, _ = cli("validate", f"{run}/trip_spec.json", f"{run}/candidates.json", "--out", f"{run}/shortlist.json", "--run", run)
        self.assertEqual(code, 0)

        # The pick must quote the user.
        code, nxt = cli("next", run)
        self.assertEqual((code, nxt["stage"]), (2, "APPROVE"))
        self.assertTrue(nxt["approval_cards"])
        with self.assertRaises(SystemExit):
            cli("approve", run, "--pick", 1)
        self.assertEqual(cli("approve", run, "--pick", 1, "--user-said", "ok go ahead")[0], 1)
        self.assertEqual(cli("approve", run, "--pick", 1, "--user-said", "Let's do the first one")[0], 0)

        # Checkout jumped 6%: blocked.
        pick = rjson(f"{run}/approval.json")["option"]
        live = {"seller": "www." + pick["seller"], "total_price": round(pick["price_seen"] * 1.06, 2), "currency": "USD",
                "travelers": 2, "flights": pick["flights"], "depart_date": pick["depart_date"]}
        wjson(f"{run}/live.json", live)
        self.assertEqual(cli("next", run)[1]["stage"], "PRECHECK")
        pre = ("precheck", f"{run}/trip_spec.json", f"{run}/shortlist.json", "--pick", 1, "--live", f"{run}/live.json", "--run", run)
        self.assertEqual(cli(*pre)[0], 2)
        code, nxt = cli("next", run)
        self.assertEqual((code, nxt["stage"]), (2, "PRECHECK"))
        self.assertIn("blocked", nxt["status"])

        # Recaptured page that has not been prechecked yet is not trusted.
        live["total_price"] = pick["price_seen"]
        wjson(f"{run}/live.json", live)
        self.assertEqual(cli("next", run)[1]["missing"], ["precheck result"])
        self.assertEqual(cli(*pre)[0], 0)

        code, nxt = cli("next", run)
        self.assertEqual((code, nxt["stage"]), (0, "PAY"))
        self.assertIn(f"{pick['price_seen']:.2f}", nxt["status"])

        cli("log", run, "booking", "--summary", "ABC123, seats 31A 31B")
        self.assertEqual(cli("next", run)[1]["stage"], "SERVICES")
        cli("log", run, "service_request", "--summary", "VGML and WCHR confirmed")
        code, nxt = cli("next", run)
        self.assertEqual((code, nxt["stage"]), (0, "DONE"))
        code, text = cli("receipt", run)
        for word in ("plan", "page_scan", "approval", "precheck", "booking", "service_request"):
            self.assertIn(word, text)

    def test_dry_run_stops_before_pay(self):
        run = self.run
        cli("intake", run, "--set", "origin=SFO", "--set", "destination=MAA")
        code, out = answer_everything(run, self.start, "--dry-run")
        self.assertIn("DRY RUN", out["summary_for_user"])
        cli("intake", run, "--confirm")
        wjson(f"{run}/candidates.json", shift(json.loads((EX / "candidates.example.json").read_text()), self.offset))
        scan_all(run)
        cli("validate", f"{run}/trip_spec.json", f"{run}/candidates.json", "--out", f"{run}/shortlist.json", "--run", run)
        cli("approve", run, "--pick", 1, "--user-said", "option 1")
        pick = rjson(f"{run}/approval.json")["option"]
        wjson(f"{run}/live.json", {"seller": pick["seller"], "total_price": pick["price_seen"], "currency": "USD",
                                   "travelers": 2, "flights": pick["flights"], "depart_date": pick["depart_date"]})
        cli("precheck", f"{run}/trip_spec.json", f"{run}/shortlist.json", "--pick", 1, "--live", f"{run}/live.json", "--run", run)
        code, nxt = cli("next", run)
        self.assertEqual((code, nxt["stage"]), (2, "DRY_RUN_COMPLETE"))

    def test_changing_an_answer_needs_reconfirmation(self):
        run = self.run
        cli("intake", run, "--set", "origin=SFO", "--set", "destination=MAA")
        answer_everything(run, self.start)
        cli("intake", run, "--confirm")
        self.assertTrue(os.path.exists(f"{run}/trip_spec.json"))
        code, out = cli("intake", run, "--set", "travelers=3")
        self.assertEqual(out["state"], "needs_user_confirmation")
        self.assertFalse(os.path.exists(f"{run}/trip_spec.json"))

    def test_memory_answers_are_labelled(self):
        run = self.run
        cli("intake", run, "--set", "origin=SFO", "--source", "memory")
        code, out = cli("intake", run, "--set", "destination=MAA")
        code, out = answer_everything(run, self.start)
        self.assertIn("SFO (from memory) to MAA", out["summary_for_user"])

    def test_nothing_passes_needs_user(self):
        run = self.run
        os.makedirs(run)
        spec = json.loads((EX / "trip_spec.example.json").read_text())
        spec["hard"]["price_cap_total"] = 100
        wjson(f"{run}/trip_spec.json", spec)
        (Path(run) / "candidates.json").write_text((EX / "candidates.example.json").read_text())
        scan_all(run)
        cli("validate", f"{run}/trip_spec.json", f"{run}/candidates.json", "--out", f"{run}/shortlist.json")
        code, nxt = cli("next", run)
        self.assertEqual((code, nxt["stage"], nxt["needs_user"]), (2, "VALIDATE", True))
        self.assertTrue(nxt["rejected"])


if __name__ == "__main__":
    unittest.main()
