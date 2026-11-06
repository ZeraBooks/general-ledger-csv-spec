#!/usr/bin/env python3
"""Check a chart of accounts, a journal and trial balances against each other.

    python3 cli/gl_check.py --coa chart.csv
    python3 cli/gl_check.py --coa chart.csv --journal journal.csv --start 2026-07-01 --end 2026-07-31
    python3 cli/gl_check.py --coa chart.csv --journal journal.csv --opening tb-june.csv --closing tb-july.csv
    python3 cli/gl_check.py --coa chart.csv --journal journal.csv --opening tb-june.csv --build-tb out.csv

Rules: rules/ledger-rules.csv. Exit code 0 = no errors, 1 = errors,
2 = a file could not be read. Python 3.8+, standard library only.

Part of https://github.com/ZeraBooks/general-ledger-csv-spec
(ZeraBooks, https://www.zerabooks.com/general-ledger-software).
"""
import argparse
import csv
import datetime as dt
import json
import re
import sys
from decimal import Decimal

AMOUNT = re.compile(r"^[0-9]+\.[0-9]{2}$")
TYPES = {"asset", "liability", "equity", "revenue", "expense"}
NORMAL = {"asset": "debit", "expense": "debit", "liability": "credit", "equity": "credit", "revenue": "credit"}
CONTRA = re.compile(r"accumulated|draw|distribution|return|discount|allowance|contra", re.I)
RANGES = {"asset": [(1000, 1999)], "liability": [(2000, 2999)], "equity": [(3000, 3999)],
          "revenue": [(4000, 4999), (8000, 8499)], "expense": [(5000, 7999), (8500, 9999)]}
ZERO = Decimal("0")


class Issue:
    def __init__(self, rule, severity, where, message):
        self.rule, self.severity, self.where, self.message = rule, severity, where, message

    def __repr__(self):
        return f"{self.severity.upper():7} {self.rule} {self.where}: {self.message}"


def read(path, needed, issues, label):
    with open(path, encoding="utf-8-sig", newline="") as fh:
        r = csv.DictReader(fh)
        missing = [c for c in needed if c not in (r.fieldnames or [])]
        if missing:
            issues.append(Issue("GL-001", "error", label, f"missing columns: {', '.join(missing)}"))
            return []
        return [{k: (v or "").strip() for k, v in row.items()} for row in r]


def amount(v, issues, where):
    if v == "":
        return ZERO
    if not AMOUNT.match(v):
        issues.append(Issue("GL-001", "error", where, f"'{v}' is not a positive amount with two decimals"))
        return ZERO
    return Decimal(v)


def check_chart(path, issues):
    rows = read(path, ["account_number", "account_name", "account_type", "normal_balance"], issues, "chart")
    chart = {}
    parents = set()
    for n, r in enumerate(rows, start=2):
        where = f"chart line {n}"
        num, typ = r["account_number"], r["account_type"]
        if num in chart:
            issues.append(Issue("GL-002", "error", where, f"account {num} listed twice"))
            continue
        if typ not in TYPES:
            issues.append(Issue("GL-003", "error", where, f"type '{typ}' for {num}"))
            continue
        if r["normal_balance"] != NORMAL[typ] and not CONTRA.search(r["account_name"]):
            issues.append(Issue("GL-004", "warning", where, f"{num} {r['account_name']}: {typ} with a {r['normal_balance']} normal balance"))
        try:
            base = int(num.split("-")[0][:4])
            if not any(lo <= base <= hi for lo, hi in RANGES[typ]):
                issues.append(Issue("GL-005", "warning", where, f"{num} is outside this spec's range for {typ}"))
        except ValueError:
            issues.append(Issue("GL-005", "warning", where, f"{num} is not numeric"))
        if r.get("parent_account"):
            parents.add(r["parent_account"])
        chart[num] = r
    for num in chart:
        chart[num]["_is_parent"] = num in parents
    return chart


def check_journal(path, chart, issues, start=None, end=None):
    rows = read(path, ["entry_id", "date", "account_number", "debit", "credit"], issues, "journal")
    entries = {}
    movement = {}
    for n, r in enumerate(rows, start=2):
        where = f"journal line {n}"
        d, c = amount(r["debit"], issues, where), amount(r["credit"], issues, where)
        if (d > 0) == (c > 0):
            issues.append(Issue("GL-007", "error", where, f"entry {r['entry_id']}: fill exactly one of debit or credit"))
        acct = r["account_number"]
        if acct not in chart:
            issues.append(Issue("GL-009", "error", where, f"account {acct} is not in the chart of accounts"))
        else:
            if chart[acct].get("active", "yes") == "no":
                issues.append(Issue("GL-010", "warning", where, f"posting to inactive account {acct}"))
            if chart[acct]["_is_parent"]:
                issues.append(Issue("GL-010", "warning", where, f"posting to parent account {acct}; use a sub-account"))
        e = entries.setdefault(r["entry_id"], {"lines": [], "dates": set(), "first": n})
        e["lines"].append((acct, d, c))
        e["dates"].add(r["date"])
        movement[acct] = movement.get(acct, ZERO) + d - c
    sigs = {}
    for eid, e in entries.items():
        where = f"entry {eid}"
        dr = sum(x[1] for x in e["lines"])
        cr = sum(x[2] for x in e["lines"])
        if dr != cr:
            issues.append(Issue("GL-006", "error", where, f"debits {dr} vs credits {cr} (off by {dr - cr})"))
        if len(e["lines"]) < 2 or len(e["dates"]) != 1:
            issues.append(Issue("GL-008", "error", where, f"{len(e['lines'])} line(s), {len(e['dates'])} date(s)"))
        for ds in e["dates"]:
            try:
                day = dt.date.fromisoformat(ds)
            except ValueError:
                issues.append(Issue("GL-011", "error", where, f"date '{ds}' is not YYYY-MM-DD"))
                continue
            if (start and day < start) or (end and day > end):
                issues.append(Issue("GL-011", "error", where, f"{ds} is outside {start} to {end}"))
        sig = (tuple(sorted(e["dates"])), tuple(sorted(e["lines"])))
        if sig in sigs:
            issues.append(Issue("GL-017", "warning", where, f"same date, accounts and amounts as entry {sigs[sig]}"))
        else:
            sigs[sig] = eid
    return entries, movement


def read_tb(path, chart, issues, label):
    rows = read(path, ["account_number", "debit", "credit"], issues, label)
    bal = {}
    td = tc = ZERO
    for n, r in enumerate(rows, start=2):
        where = f"{label} line {n}"
        d, c = amount(r["debit"], issues, where), amount(r["credit"], issues, where)
        if d > 0 and c > 0:
            issues.append(Issue("GL-013", "error", where, f"{r['account_number']} has both a debit and a credit balance"))
        if chart is not None and r["account_number"] not in chart:
            issues.append(Issue("GL-013", "error", where, f"account {r['account_number']} is not in the chart"))
        bal[r["account_number"]] = bal.get(r["account_number"], ZERO) + d - c
        td += d
        tc += c
    if td != tc:
        issues.append(Issue("GL-012", "error", label, f"total debits {td} vs total credits {tc} (off by {td - tc})"))
    return bal, td


def tb_checks(bal, chart, issues, label, ytd_start_equity_only=False):
    sums = {t: ZERO for t in TYPES}
    for acct, b in bal.items():
        if acct not in chart:
            continue
        typ = chart[acct]["account_type"]
        sums[typ] += b
        side = "debit" if b > 0 else "credit" if b < 0 else None
        if side and side != chart[acct]["normal_balance"] and not CONTRA.search(chart[acct]["account_name"]):
            issues.append(Issue("GL-015", "warning", label, f"{acct} {chart[acct]['account_name']} has a {side} balance of {abs(b)}"))
    # Debit-positive balances: assets + expenses = -(liabilities + equity + revenue)
    assets = sums["asset"]
    liab, equity = -sums["liability"], -sums["equity"]
    net_income = -sums["revenue"] - sums["expense"]
    if assets != liab + equity + net_income:
        issues.append(Issue("GL-016", "error", label, f"assets {assets} vs liabilities {liab} + equity {equity} + net income {net_income}"))
    return {"assets": str(assets), "liabilities": str(liab), "equity": str(equity), "net_income": str(net_income)}


def write_tb(path, bal, chart):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["account_number", "account_name", "account_type", "debit", "credit"])
        for acct in sorted(bal):
            b = bal[acct]
            if b == 0:
                continue
            c = chart.get(acct, {})
            w.writerow([acct, c.get("account_name", ""), c.get("account_type", ""), f"{b:.2f}" if b > 0 else "", f"{-b:.2f}" if b < 0 else ""])


def run(coa, journal=None, opening=None, closing=None, start=None, end=None, build_tb=None):
    issues = []
    summary = {}
    chart = check_chart(coa, issues)
    summary["accounts"] = len(chart)
    movement = {}
    if journal:
        entries, movement = check_journal(journal, chart, issues, start, end)
        summary["entries"] = len(entries)
        summary["lines"] = sum(len(e["lines"]) for e in entries.values())
    open_bal = None
    if opening:
        open_bal, _ = read_tb(opening, chart, issues, "opening TB")
    if opening and (journal or build_tb):
        rolled = dict(open_bal)
        for a, m in movement.items():
            rolled[a] = rolled.get(a, ZERO) + m
        if build_tb:
            write_tb(build_tb, rolled, chart)
    if closing:
        close_bal, total = read_tb(closing, chart, issues, "closing TB")
        summary["closing_tb_total"] = str(total)
        summary.update(tb_checks(close_bal, chart, issues, "closing TB"))
        if open_bal is not None and journal:
            for acct in sorted(set(rolled) | set(close_bal)):
                want, got = rolled.get(acct, ZERO), close_bal.get(acct, ZERO)
                if want != got:
                    name = chart.get(acct, {}).get("account_name", "")
                    issues.append(Issue("GL-014", "error", f"account {acct}", f"{name}: opening + journal = {want}, closing TB shows {got} (off by {got - want})"))
    return issues, summary


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check a chart of accounts, journal and trial balances.")
    ap.add_argument("--coa", required=True)
    ap.add_argument("--journal")
    ap.add_argument("--opening", help="trial balance at the start of the period")
    ap.add_argument("--closing", help="trial balance at the end of the period")
    ap.add_argument("--start", type=dt.date.fromisoformat)
    ap.add_argument("--end", type=dt.date.fromisoformat)
    ap.add_argument("--build-tb", metavar="OUT", help="write opening TB + journal as a closing TB")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        issues, summary = run(a.coa, a.journal, a.opening, a.closing, a.start, a.end, a.build_tb)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        print(f"could not read: {exc}", file=sys.stderr)
        return 2
    errors = [i for i in issues if i.severity == "error"]
    if a.json:
        print(json.dumps({"ok": not errors, "summary": summary, "issues": [vars(i) for i in issues]}, indent=2))
    else:
        for i in issues:
            print(i)
        print(", ".join(f"{k} {v}" for k, v in summary.items()) + (". OK" if not errors else f". {len(errors)} error(s)"))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
