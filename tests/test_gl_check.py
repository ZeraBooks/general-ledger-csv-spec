import contextlib
import datetime as dt
import glob
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
import gl_check as g  # noqa: E402

MONTHS = [("06-30", "07", "07-31"), ("07-31", "08", "08-31"), ("08-31", "09", "09-30")]


class Companies(unittest.TestCase):
    def companies(self):
        return sorted(glob.glob(os.path.join(ROOT, "samples", "companies", "*")))

    def test_every_month_rolls_forward_clean(self):
        self.assertEqual(len(self.companies()), 6)
        for c in self.companies():
            for o, m, cl in MONTHS:
                issues, s = g.run(f"{c}/chart-of-accounts.csv", f"{c}/journal-2026-{m}.csv", f"{c}/tb-2026-{o}.csv",
                                  f"{c}/tb-2026-{cl}.csv", dt.date(2026, int(m), 1), dt.date.fromisoformat(f"2026-{cl}"))
                self.assertEqual(issues, [], f"{c} {m}")

    def test_build_tb_reproduces_closing(self):
        c = self.companies()[0]
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "tb.csv")
            g.run(f"{c}/chart-of-accounts.csv", f"{c}/journal-2026-08.csv", f"{c}/tb-2026-07-31.csv", build_tb=out)
            self.assertEqual(open(out).read(), open(f"{c}/tb-2026-08-31.csv").read())


class Invalid(unittest.TestCase):
    def test_each_fails_its_rule(self):
        cases = json.load(open(os.path.join(ROOT, "samples", "invalid", "expected.json"), encoding="utf-8"))
        self.assertEqual(len(cases), 17)
        for c in cases:
            f, a = os.path.join(ROOT, c["folder"]), c["args"]
            p = lambda k: a.get(k) and os.path.join(f, a[k])  # noqa: E731
            issues, _ = g.run(p("coa"), p("journal"), p("opening"), p("closing"),
                              dt.date.fromisoformat(c["start"]), dt.date.fromisoformat(c["end"]))
            self.assertIn(c["must_fail"], {i.rule for i in issues}, c["folder"])

    def test_rules_file_covers_validator(self):
        import csv
        ids = {r["rule_id"] for r in csv.DictReader(open(os.path.join(ROOT, "rules", "ledger-rules.csv"), encoding="utf-8"))}
        src = open(os.path.join(ROOT, "cli", "gl_check.py"), encoding="utf-8").read()
        self.assertEqual({f"GL-{n:03d}" for n in range(1, 40) if f'"GL-{n:03d}"' in src} - ids, set())

    def test_cli(self):
        c = os.path.join(ROOT, "samples", "invalid", "entry-out-of-balance")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(g.main(["--coa", f"{c}/chart-of-accounts.csv", "--journal", f"{c}/journal.csv"]), 1)
            ok = os.path.join(ROOT, "samples", "companies", "vega-cpa")
            self.assertEqual(g.main(["--coa", f"{ok}/chart-of-accounts.csv", "--journal", f"{ok}/journal-2026-07.csv"]), 0)


if __name__ == "__main__":
    unittest.main()
