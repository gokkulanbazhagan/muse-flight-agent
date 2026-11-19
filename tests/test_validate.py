import json
import unittest
from pathlib import Path

from flightagent import validate as v
from flightagent.guard import seller_allowed

ROOT = Path(__file__).resolve().parents[1]
SPEC = json.loads((ROOT / "examples" / "trip_spec.example.json").read_text())
CANDS = json.loads((ROOT / "examples" / "candidates.example.json").read_text())


def by_id(cid):
    return next(c for c in CANDS if c["id"] == cid)


class HardConstraints(unittest.TestCase):
    def test_good_itinerary_passes(self):
        self.assertEqual(v.check_hard(by_id("c1"), SPEC), [])

    def test_short_layover_rejected(self):
        self.assertTrue(any("layover" in r for r in v.check_hard(by_id("c3"), SPEC)))

    def test_unlisted_seller_rejected(self):
        self.assertTrue(any("not the official site" in r for r in v.check_hard(by_id("c4"), SPEC)))

    def test_lookalike_subdomain_not_allowed(self):
        self.assertFalse(seller_allowed("emirates.com.evil.example", ["emirates.com"]))
        self.assertTrue(seller_allowed("www.emirates.com", ["emirates.com"]))

    def test_bags_rejected(self):
        self.assertTrue(any("bags" in r for r in v.check_hard(by_id("c5"), SPEC)))

    def test_redeye_rejected(self):
        self.assertTrue(any("red-eye" in r for r in v.check_hard(by_id("c6"), SPEC)))


class Ranking(unittest.TestCase):
    def test_shortlist_and_drift_cap(self):
        out = v.run(SPEC, CANDS, top=3)
        self.assertEqual({s["id"] for s in out["shortlist"]}, {"c1", "c2"})
        for s in out["shortlist"]:
            self.assertAlmostEqual(s["max_price_at_checkout"], round(s["price_seen"] * 1.03, 2))
            self.assertTrue(s["flights"])

    def test_empty_result_says_why(self):
        strict = json.loads(json.dumps(SPEC))
        strict["hard"]["price_cap_total"] = 100
        out = v.run(strict, CANDS, top=3)
        self.assertEqual(out["shortlist"], [])
        self.assertIn("no option passed", out["next_step"])


if __name__ == "__main__":
    unittest.main()
