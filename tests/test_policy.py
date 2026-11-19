"""Where the agent may search and pay: airline official sites, search engines, listed agencies."""
import json
import unittest
from pathlib import Path

from flightagent import airlines, intake, policy, validate
from flightagent.candidates import check_one
from flightagent.guard import registrable

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "examples" / "trip_spec.example.json").read_text())
CANDS = json.loads((ROOT / "examples" / "candidates.example.json").read_text())


def cand(**kw):
    base = next(c for c in CANDS if c["id"] == "c1")
    return {**json.loads(json.dumps(base)), **kw}


class OfficialSites(unittest.TestCase):
    def test_airline_own_site_allowed(self):
        v = policy.seller_verdict("https://www.emirates.com/us/book", SPEC, {"EK"})
        self.assertTrue(v["allowed"])
        self.assertIn("Emirates", v["basis"])

    def test_other_airlines_site_refused(self):
        v = policy.seller_verdict("qatarairways.com", SPEC, {"EK"})
        self.assertFalse(v["allowed"])
        self.assertIn("Qatar Airways, which does not fly", v["reasons"][0])

    def test_codeshare_partner_site_allowed(self):
        # Sold as AA, operated on a BA flight number: both airlines' sites qualify.
        c = cand(carrier="AA", seller="britishairways.com",
                 segments=[dict(CANDS[0]["segments"][0], flight="BA286")])
        self.assertEqual(airlines.carriers_of(c), {"AA", "BA"})
        self.assertTrue(policy.seller_verdict(c["seller"], SPEC, airlines.carriers_of(c))["allowed"])

    def test_search_engine_is_never_a_seller(self):
        v = policy.seller_verdict("https://www.google.com/travel/flights", SPEC, {"EK"})
        self.assertFalse(v["allowed"])
        self.assertIn("search engine", v["reasons"][0])

    def test_travel_agency_needs_user_listing(self):
        self.assertFalse(policy.seller_verdict("expedia.com", SPEC, {"EK"})["allowed"])
        listed = dict(SPEC, allowed_sellers=["expedia.com"])
        v = policy.seller_verdict("www.expedia.com", listed, {"EK"})
        self.assertTrue(v["allowed"])
        self.assertEqual(v["basis"], "listed by the user")

    def test_lookalike_of_carrier_site_flagged(self):
        v = policy.seller_verdict("emirates-deals-online.example", SPEC, {"EK"})
        self.assertFalse(v["allowed"])
        self.assertTrue(any("imitation of emirates.com" in r for r in v["reasons"]))

    def test_unknown_airline_explained(self):
        v = policy.seller_verdict("someair.example", SPEC, {"ZZ"})
        self.assertTrue(any("not in the registry" in r for r in v["reasons"]))

    def test_listed_only_policy(self):
        strict = dict(SPEC, seller_policy="listed_only", allowed_sellers=["qatarairways.com"])
        self.assertFalse(policy.seller_verdict("emirates.com", strict, {"EK"})["allowed"])
        self.assertTrue(policy.seller_verdict("qatarairways.com", strict, {"QR"})["allowed"])

    def test_old_specs_keep_their_allowlist(self):
        old = {k: v for k, v in SPEC.items() if k != "seller_policy"}
        old["allowed_sellers"] = ["qatarairways.com"]
        self.assertEqual(policy.seller_policy(old), "listed_only")

    def test_registry_domains_are_well_formed(self):
        for code, (name, doms) in airlines.REGISTRY.items():
            self.assertRegex(code, r"^[A-Z0-9]{2}$")
            for d in doms:
                self.assertEqual(registrable(d), d, f"{name}: {d}")


class SearchSources(unittest.TestCase):
    def test_result_from_google_flights_ok(self):
        c = cand(source_url="https://www.google.com/travel/flights/search?tfs=x")
        self.assertEqual(check_one(c, SPEC), [])

    def test_result_from_random_site_refused(self):
        c = cand(source_url="https://cheapflights-blog.example/deal")
        self.assertTrue(any("search engine" in e for e in check_one(c, SPEC)))


class Preferences(unittest.TestCase):
    def test_avoided_airline_rejected(self):
        spec = dict(SPEC, avoid_airlines=["EK"])
        self.assertTrue(any("avoid" in r for r in validate.check_hard(cand(), spec)))

    def test_preferred_airline_ranks_higher(self):
        base = validate.run(SPEC, CANDS, 3)["shortlist"]
        pref = validate.run(dict(SPEC, preferred_airlines=["EK"]), CANDS, 3)["shortlist"]
        self.assertGreater(next(o["score"] for o in pref if o["id"] == "c1"),
                           next(o["score"] for o in base if o["id"] == "c1"))

    def test_shortlist_records_why_seller_is_ok(self):
        top = validate.run(SPEC, CANDS, 3)["shortlist"][0]
        self.assertTrue(top["seller_basis"].startswith("official"))
        self.assertTrue(top["carriers"])


class IntakeQuestions(unittest.TestCase):
    def test_bad_airline_code_bounced(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = intake.intake(d, ["preferred_airlines=Singapore Airlines"])
            self.assertTrue(any("2-character" in e for e in out["errors"]))

    def test_summary_explains_search_and_booking(self):
        import tempfile
        from datetime import date, timedelta
        start = (date.today() + timedelta(days=30)).isoformat()
        with tempfile.TemporaryDirectory() as d:
            out = intake.intake(d, ["origin=SFO", "destination=MAA", f"depart_earliest={start}", f"depart_latest={start}",
                                    "travelers=3", "price_cap_total=2000", "traveler_profile=family",
                                    "preferred_airlines=SQ", "extra_sellers=expedia.com"], accept_defaults=True)
            text = out["summary_for_user"]
            for words in ("Google Flights", "Skyscanner", "each airline's own website", "expedia.com",
                          "prefer Singapore Airlines", "profile 'family'", "Cabin: economy (default)"):
                self.assertIn(words, text)


if __name__ == "__main__":
    unittest.main()
