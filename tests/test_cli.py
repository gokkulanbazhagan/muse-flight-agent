import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from flightagent.cli import main

ROOT = Path(__file__).resolve().parents[1]
EX = ROOT / "examples"


def run(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main([str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


class EndToEnd(unittest.TestCase):
    """The full booking loop, exactly as the agent runs it, minus the browser."""

    def test_full_loop(self):
        with tempfile.TemporaryDirectory() as d:
            runs = os.path.join(d, "runs", "parents-maa")
            shortlist = os.path.join(d, "shortlist.json")

            self.assertEqual(run("check-spec", EX / "trip_spec.example.json")[0], 0)
            self.assertEqual(run("scan-page", EX / "pages" / "clean_fare_page.txt", "--run", runs, "--site", "emirates.com")[0], 0)
            self.assertEqual(run("scan-page", EX / "pages" / "injected_fare_page.txt", "--run", runs, "--site", "deals.example")[0], 2)

            code, out, err = run("validate", EX / "trip_spec.example.json", EX / "candidates.example.json", "--out", shortlist, "--run", runs)
            self.assertEqual(code, 0)
            self.assertIn("Option 1", out)
            self.assertIn("rejected c4", err)

            self.assertEqual(run("precheck", EX / "trip_spec.example.json", shortlist, "--pick", 1, "--live", EX / "live_checkout.ok.json", "--run", runs)[0], 0)
            code, out, _ = run("precheck", EX / "trip_spec.example.json", shortlist, "--pick", 1, "--live", EX / "live_checkout.drift.json", "--run", runs)
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(out)["verdict"], "BLOCK")

            self.assertEqual(run("log", runs, "booking", "--summary", "confirmation code recorded")[0], 0)
            code, out, _ = run("receipt", runs)
            self.assertIn("Suspected prompt injections", out)
            self.assertIn("precheck", out)

    def test_selftest(self):
        code, out, _ = run("selftest")
        self.assertEqual(code, 0)
        self.assertIn("STATUS: ready", out)


if __name__ == "__main__":
    unittest.main()
