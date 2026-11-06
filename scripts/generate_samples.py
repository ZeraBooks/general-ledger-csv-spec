"""Generate fictional company ledgers in samples/companies/.

    python3 scripts/generate_samples.py

For each of 6 fictional companies:
  chart-of-accounts.csv
  tb-2026-06-30.csv                 opening trial balance (year to date)
  journal-2026-07.csv ... -09.csv   every journal entry for the month
  tb-2026-07-31.csv ... -09-30.csv  trial balance at each month end
Every entry balances and every trial balance equals the one before plus
the month's journal. Seeded, so the output is the same on every run.
samples/invalid/ gets one broken file set per rule.
"""
import csv
import datetime as dt
import json
import os
import random
import shutil
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "samples")
COA_COLS = ["account_number", "account_name", "account_type", "account_subtype", "normal_balance", "parent_account", "active"]
J_COLS = ["entry_id", "date", "account_number", "account_name", "description", "debit", "credit", "entry_type", "source", "reference"]
TB_COLS = ["account_number", "account_name", "account_type", "debit", "credit"]

BASE_COA = [
    ("1000", "Operating Checking", "asset", "bank"), ("1010", "Savings", "asset", "bank"),
    ("1100", "Accounts Receivable", "asset", "accounts_receivable"), ("1200", "Inventory", "asset", "other_current_asset"),
    ("1300", "Prepaid Insurance", "asset", "other_current_asset"), ("1500", "Equipment", "asset", "fixed_asset"),
    ("1510", "Accumulated Depreciation - Equipment", "asset", "accumulated_depreciation"),
    ("2000", "Accounts Payable", "liability", "accounts_payable"), ("2100", "Business Credit Card", "liability", "credit_card"),
    ("2200", "Payroll Liabilities", "liability", "other_current_liability"), ("2300", "Sales Tax Payable", "liability", "other_current_liability"),
    ("2700", "Equipment Loan", "liability", "long_term_liability"),
    ("3000", "Owner's Capital", "equity", "owner_equity"), ("3100", "Owner's Draws", "equity", "owner_equity"),
    ("3900", "Retained Earnings", "equity", "retained_earnings"),
    ("4000", "{rev1}", "revenue", "income"), ("4100", "{rev2}", "revenue", "income"), ("4900", "Sales Returns and Discounts", "revenue", "income"),
    ("5000", "{cogs}", "expense", "cost_of_sales"),
    ("6000", "Wages", "expense", "operating_expense"), ("6010", "Payroll Taxes", "expense", "operating_expense"),
    ("6100", "Rent", "expense", "operating_expense"), ("6200", "Utilities", "expense", "operating_expense"),
    ("6300", "Insurance", "expense", "operating_expense"), ("6400", "Supplies", "expense", "operating_expense"),
    ("6500", "Software and Subscriptions", "expense", "operating_expense"), ("6600", "Bank and Card Fees", "expense", "operating_expense"),
    ("6700", "Vehicle and Fuel", "expense", "operating_expense"), ("6800", "Depreciation", "expense", "operating_expense"),
    ("6900", "Professional Fees", "expense", "operating_expense"), ("8500", "Interest Expense", "expense", "other_expense"),
    ("8000", "Interest Income", "revenue", "other_income"),
]
COMPANIES = [
    ("juniper-lane-bakery", "Juniper Lane Bakery LLC", {"rev1": "Bakery Sales", "rev2": "Wholesale and Catering", "cogs": "Ingredients and Packaging"}, True, 1.0),
    ("okafor-family-dental", "Okafor Family Dental PC", {"rev1": "Patient Fees", "rev2": "Insurance Reimbursements", "cogs": "Dental Lab and Supplies"}, False, 2.4),
    ("brightwater-landscaping", "Brightwater Landscaping Inc", {"rev1": "Maintenance Contracts", "rev2": "Installation Projects", "cogs": "Plants, Materials and Subcontractors"}, True, 1.7),
    ("redline-freight", "Redline Freight Co", {"rev1": "Freight Revenue", "rev2": "Fuel Surcharge Revenue", "cogs": "Fuel and Tolls"}, False, 3.1),
    ("vega-cpa", "Marisol Vega CPA", {"rev1": "Tax Preparation Fees", "rev2": "Monthly Bookkeeping Fees", "cogs": "Contract Preparer Costs"}, False, 0.8),
    ("copperline-electric", "Copperline Electric LLC", {"rev1": "Service Calls", "rev2": "Contract Jobs", "cogs": "Electrical Materials"}, True, 2.0),
]
NAMES = {}


def money(rng, lo, hi, scale=1.0):
    return (Decimal(rng.randint(int(lo * 100), int(hi * 100))) * Decimal(str(scale)) / 100).quantize(Decimal("0.01"))


def write(path, cols, rows):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)


def tb_rows(bal, chart):
    rows = []
    for a in sorted(bal):
        b = bal[a]
        if b == 0:
            continue
        rows.append({"account_number": a, "account_name": chart[a]["account_name"], "account_type": chart[a]["account_type"],
                     "debit": f"{b:.2f}" if b > 0 else "", "credit": f"{-b:.2f}" if b < 0 else ""})
    return rows


def main():
    rng = random.Random(20261105)
    for sub in ("companies", "invalid"):
        shutil.rmtree(os.path.join(OUT, sub), ignore_errors=True)
        os.makedirs(os.path.join(OUT, sub))
    index = []
    for slug, name, labels, sales_tax, scale in COMPANIES:
        folder = os.path.join(OUT, "companies", slug)
        os.makedirs(folder)
        chart = {}
        for num, nm, typ, sub in BASE_COA:
            if num == "2300" and not sales_tax:
                continue
            if num == "1200" and slug in ("vega-cpa", "okafor-family-dental"):
                continue
            nb = "credit" if typ in ("liability", "equity", "revenue") else "debit"
            if num in ("1510",):
                nb = "credit"
            if num in ("3100", "4900"):
                nb = "debit"
            chart[num] = {"account_number": num, "account_name": nm.format(**labels), "account_type": typ, "account_subtype": sub,
                          "normal_balance": nb, "parent_account": "", "active": "yes"}
        write(os.path.join(folder, "chart-of-accounts.csv"), COA_COLS, [chart[k] for k in sorted(chart)])

        # Opening TB at June 30, 2026, half a year in. Retained earnings is the plug.
        s = scale
        bal = {"1000": money(rng, 18000, 42000, s), "1010": money(rng, 10000, 30000, s), "1100": money(rng, 6000, 20000, s),
               "1300": money(rng, 1800, 3600, s), "1500": money(rng, 40000, 90000, s), "1510": -money(rng, 8000, 20000, s),
               "2000": -money(rng, 3000, 9000, s), "2100": -money(rng, 1200, 4800, s), "2200": -money(rng, 2000, 6000, s),
               "2700": -money(rng, 20000, 45000, s), "3000": -money(rng, 10000, 25000, s), "3100": money(rng, 12000, 30000, s),
               "4000": -money(rng, 120000, 180000, s), "4100": -money(rng, 40000, 80000, s), "4900": money(rng, 400, 2500, s),
               "5000": money(rng, 30000, 60000, s), "6000": money(rng, 45000, 70000, s), "6010": money(rng, 4000, 7000, s),
               "6100": money(rng, 18000, 18000, s), "6200": money(rng, 3000, 5000, s), "6300": money(rng, 2400, 3600, s),
               "6400": money(rng, 1500, 4000, s), "6500": money(rng, 900, 2200, s), "6600": money(rng, 600, 1800, s),
               "6700": money(rng, 2000, 9000, s), "6800": money(rng, 3000, 6000, s), "6900": money(rng, 1500, 4000, s),
               "8500": money(rng, 700, 1500, s), "8000": -money(rng, 50, 300, s)}
        if "1200" in chart:
            bal["1200"] = money(rng, 3000, 9000, s)
        if "2300" in chart:
            bal["2300"] = -money(rng, 900, 3000, s)
        plug = -sum(bal.values())
        if plug > -5000:
            # Keep retained earnings a credit balance of at least $5,000.
            bal["3000"] += plug + money(rng, 5000, 15000, s)
        bal["3900"] = -sum(bal.values())
        write(os.path.join(folder, "tb-2026-06-30.csv"), TB_COLS, tb_rows(bal, chart))

        seq = [0]
        for m in (7, 8, 9):
            start = dt.date(2026, m, 1)
            end = dt.date(2026, m + 1, 1) - dt.timedelta(days=1)
            lines = []

            def entry(day, desc, src, ref, parts, etype="standard"):
                seq[0] += 1
                eid = f"JE-2026-{seq[0]:04d}"
                for acct, dr, cr in parts:
                    lines.append({"entry_id": eid, "date": day.isoformat(), "account_number": acct, "account_name": chart[acct]["account_name"],
                                  "description": desc, "debit": f"{dr:.2f}" if dr else "", "credit": f"{cr:.2f}" if cr else "",
                                  "entry_type": etype, "source": src, "reference": ref})
                    bal[acct] = bal.get(acct, Decimal("0")) + (dr or 0) - (cr or 0)

            for wk in range(4):
                day = start + dt.timedelta(days=wk * 7 + 3)
                amt = money(rng, 6000, 11000, s)
                if "2300" in chart:
                    tax = (amt * Decimal("0.0725")).quantize(Decimal("0.01"))
                    entry(day, "Weekly deposits", "Bank statement", f"DEP {day:%m%d}", [("1000", amt + tax, None), ("4000", None, amt), ("2300", None, tax)])
                else:
                    entry(day, "Weekly deposits", "Bank statement", f"DEP {day:%m%d}", [("1000", amt, None), ("4000", None, amt)])
            for i in range(rng.randint(3, 6)):
                day = start + dt.timedelta(days=rng.randint(0, 27))
                amt = money(rng, 1500, 6000, s)
                entry(day, f"Invoice {m}{i:02d}", "Invoice", f"INV-{m}{i:02d}", [("1100", amt, None), ("4100", None, amt)])
            ar_in = min(money(rng, 8000, 16000, s), bal["1100"])
            entry(start + dt.timedelta(days=17), "Customer payments received", "Bank statement", "ACH batch", [("1000", ar_in, None), ("1100", None, ar_in)])
            for half in (14, 28):
                gross = money(rng, 7000, 11000, s)
                er_tax = (gross * Decimal("0.0765")).quantize(Decimal("0.01"))
                withheld = (gross * Decimal("0.22")).quantize(Decimal("0.01"))
                entry(start + dt.timedelta(days=half), "Payroll", "Payroll report", f"PR {m}/{half + 1}",
                      [("6000", gross, None), ("6010", er_tax, None), ("1000", None, gross - withheld), ("2200", None, withheld + er_tax)])
            remit = -bal["2200"] - money(rng, 500, 1500, s)
            if remit > 0:
                entry(start + dt.timedelta(days=15), "Payroll tax deposit", "Bank statement", "EFTPS", [("2200", remit, None), ("1000", None, remit)])
            entry(start, "Rent", "Bank statement", "ACH", [("6100", Decimal("3000.00") * Decimal(str(s)), None), ("1000", None, Decimal("3000.00") * Decimal(str(s)))])
            bills = []
            for acct, lo, hi in (("5000", 4000, 9000), ("6200", 450, 900), ("6400", 200, 700)):
                amt = money(rng, lo, hi, s)
                bills.append(amt)
                entry(start + dt.timedelta(days=rng.randint(2, 12)), f"Bill: {chart[acct]['account_name']}", "Bill", f"BILL-{m}{acct}", [(acct, amt, None), ("2000", None, amt)])
            pay_ap = min(-bal["2000"], sum(bills) + money(rng, 0, 2000, s))
            entry(start + dt.timedelta(days=20), "Vendor payments", "Bank statement", "CHK batch", [("2000", pay_ap, None), ("1000", None, pay_ap)])
            card = [("6500", money(rng, 150, 400, s)), ("6700", money(rng, 300, 1400, s)), ("6400", money(rng, 80, 300, s))]
            for acct, amt in card:
                entry(start + dt.timedelta(days=rng.randint(1, 26)), f"Card: {chart[acct]['account_name']}", "Card statement", "CARD", [(acct, amt, None), ("2100", None, amt)])
            card_pay = -bal["2100"]
            entry(start + dt.timedelta(days=24), "Credit card payment", "Bank statement", "CARD PMT", [("2100", card_pay, None), ("1000", None, card_pay)])
            if "2300" in chart and m in (7, 9):
                st = -bal["2300"]
                entry(start + dt.timedelta(days=19), "Sales tax return paid", "Bank statement", "STATE DOR", [("2300", st, None), ("1000", None, st)])
            interest = (-bal["2700"] * Decimal("0.07") / 12).quantize(Decimal("0.01"))
            principal = money(rng, 600, 600, s)
            entry(start + dt.timedelta(days=9), "Equipment loan payment", "Bank statement", "LOAN", [("2700", principal, None), ("8500", interest, None), ("1000", None, principal + interest)])
            fee = money(rng, 40, 160, s)
            entry(end, "Bank and merchant fees", "Bank statement", "FEES", [("6600", fee, None), ("1000", None, fee)])
            intr = money(rng, 8, 40, s)
            entry(end, "Interest earned", "Bank statement", "INT", [("1010", intr, None), ("8000", None, intr)])
            draw = money(rng, 1500, 4000, s)
            entry(start + dt.timedelta(days=rng.randint(1, 25)), "Owner draw", "Bank statement", "XFER", [("3100", draw, None), ("1000", None, draw)])
            if bal["1000"] < 5000:
                move = Decimal("8000.00")
                entry(start + dt.timedelta(days=21), "Transfer from savings", "Bank statement", "XFER", [("1000", move, None), ("1010", None, move)])
            dep = (Decimal("750.00") * Decimal(str(s))).quantize(Decimal("0.01"))
            entry(end, "Monthly depreciation", "Fixed asset schedule", "DEP", [("6800", dep, None), ("1510", None, dep)], "adjusting")
            ins = (Decimal("300.00") * Decimal(str(s))).quantize(Decimal("0.01"))
            entry(end, "Prepaid insurance used", "Prepaid schedule", "PREPAID", [("6300", ins, None), ("1300", None, ins)], "adjusting")
            if "1200" in chart:
                adj = money(rng, -400, 400, s)
                if adj > 0:
                    entry(end, "Inventory count adjustment", "Inventory count", "COUNT", [("1200", adj, None), ("5000", None, adj)], "adjusting")
                elif adj < 0:
                    entry(end, "Inventory count adjustment", "Inventory count", "COUNT", [("5000", -adj, None), ("1200", None, -adj)], "adjusting")
            lines.sort(key=lambda r: (r["date"], r["entry_id"]))
            write(os.path.join(folder, f"journal-2026-{m:02d}.csv"), J_COLS, lines)
            write(os.path.join(folder, f"tb-{end.isoformat()}.csv"), TB_COLS, tb_rows(bal, chart))
            index.append([slug, name, f"2026-{m:02d}", len({l['entry_id'] for l in lines}), len(lines),
                          f"{sum(Decimal(r['debit'] or 0) for r in tb_rows(bal, chart)):.2f}"])
        NAMES[slug] = name
    with open(os.path.join(OUT, "index.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\r\n")
        w.writerow(["company", "name", "month", "entries", "lines", "closing_tb_total_debits"])
        w.writerows(index)
    make_invalid()
    print(f"{len(COMPANIES)} companies, {sum(r[3] for r in index)} entries")


def make_invalid():
    src = os.path.join(OUT, "companies", "juniper-lane-bakery")
    cases = []

    def load(name):
        return list(csv.DictReader(open(os.path.join(src, name), encoding="utf-8")))

    def case(name, rule, why, files, period=("2026-08-01", "2026-08-31")):
        folder = os.path.join(OUT, "invalid", name)
        os.makedirs(folder)
        for fname, (cols, rows) in files.items():
            write(os.path.join(folder, fname), cols, rows)
        args = {"coa": "chart-of-accounts.csv"}
        for k in ("journal", "opening", "closing"):
            f = {"journal": "journal.csv", "opening": "opening-tb.csv", "closing": "closing-tb.csv"}[k]
            if f in files:
                args[k] = f
        cases.append({"folder": f"samples/invalid/{name}", "must_fail": rule, "what_is_wrong": why, "args": args, "start": period[0], "end": period[1]})

    coa, j, o, c = load("chart-of-accounts.csv"), load("journal-2026-08.csv"), load("tb-2026-07-31.csv"), load("tb-2026-08-31.csv")

    def cp(rows):
        return [dict(r) for r in rows]

    def full(coa_=None, j_=None, o_=None, c_=None):
        return {"chart-of-accounts.csv": (COA_COLS, coa_ or cp(coa)), "journal.csv": (J_COLS, j_ or cp(j)),
                "opening-tb.csv": (TB_COLS, o_ or cp(o)), "closing-tb.csv": (TB_COLS, c_ or cp(c))}

    x = cp(j); x[0]["debit"] = "$" + x[0]["debit"] if x[0]["debit"] else x[0]["debit"]; x[0]["credit"] = x[0]["credit"] and "$" + x[0]["credit"]
    case("dollar-signs", "GL-001", "amounts with $ signs", full(j_=x))
    x = cp(coa); x.append(dict(x[0], account_name="Checking (duplicate)"))
    case("duplicate-account-number", "GL-002", "account 1000 listed twice", full(coa_=x))
    x = cp(coa); x[2]["account_type"] = "current asset"
    case("unknown-account-type", "GL-003", "type 'current asset' instead of asset", full(coa_=x))
    x = cp(coa); x[-1]["normal_balance"] = "credit" if x[-1]["normal_balance"] == "debit" else "debit"
    case("wrong-normal-balance", "GL-004", "an account with the wrong normal balance (warning)", full(coa_=x))
    x = cp(coa); x.append({"account_number": "4500", "account_name": "Office Furniture", "account_type": "asset", "account_subtype": "fixed_asset", "normal_balance": "debit", "parent_account": "", "active": "yes"})
    case("number-out-of-range", "GL-005", "an asset numbered in the revenue range (warning)", full(coa_=x))
    x = cp(j); x[1]["debit"], x[1]["credit"] = (f"{Decimal(x[1]['debit']) + 10:.2f}", "") if x[1]["debit"] else ("", f"{Decimal(x[1]['credit']) + 10:.2f}")
    case("entry-out-of-balance", "GL-006", "one line typed $10 high", full(j_=x))
    x = cp(j); x[0]["credit"] = x[0]["debit"] or x[0]["credit"]; x[0]["debit"] = x[0]["credit"]
    case("debit-and-credit-on-one-line", "GL-007", "a line with both a debit and a credit", full(j_=x))
    x = cp(j); eid = x[-1]["entry_id"]; x = [r for r in x if not (r["entry_id"] == eid and r["credit"])]
    x.append({"entry_id": "JE-SINGLE", "date": "2026-08-15", "account_number": "6400", "account_name": "Supplies", "description": "One-sided", "debit": "10.00", "credit": "", "entry_type": "standard", "source": "", "reference": ""})
    case("one-line-entry", "GL-008", "an entry with a single line", full(j_=x))
    x = cp(j); x[3]["account_number"] = "6450"
    case("account-not-in-chart", "GL-009", "a line posted to 6450, which isn't in the chart", full(j_=x))
    x = cp(coa)
    for r in x:
        if r["account_number"] == "6400":
            r["active"] = "no"
    case("inactive-account", "GL-010", "postings to an account marked inactive (warning)", full(coa_=x))
    x = cp(j); eid = x[0]["entry_id"]
    for r in x:
        if r["entry_id"] == eid:
            r["date"] = "2026-09-02"
    case("entry-outside-period", "GL-011", "a September entry in the August journal", full(j_=x))
    x = cp(c); x[0]["debit"] = f"{Decimal(x[0]['debit']) + 100:.2f}" if x[0]["debit"] else x[0]["debit"]
    case("tb-does-not-balance", "GL-012", "a trial balance with debits $100 over credits", full(c_=x))
    x = cp(c); x[1]["credit"] = "5.00" if x[1]["debit"] else x[1]["credit"]; x[1]["debit"] = x[1]["debit"] or "5.00"
    case("tb-both-sides", "GL-013", "a trial balance row with both a debit and a credit", full(c_=x))
    x = cp(j); drop = x[-1]["entry_id"]; x = [r for r in x if r["entry_id"] != drop]
    case("entry-missing-from-journal", "GL-014", "the closing TB includes an entry the journal doesn't", full(j_=x))
    x = cp(c)
    for r in x:
        if r["account_number"] == "2000":
            r["debit"], r["credit"] = r["credit"], r["debit"]
        if r["account_number"] == "3000":
            amt = Decimal(r["credit"]) + 2 * Decimal(next(q for q in c if q["account_number"] == "2000")["credit"])
            r["credit"] = f"{amt:.2f}"
    case("abnormal-balance", "GL-015", "accounts payable showing a debit balance (warning)", {"chart-of-accounts.csv": (COA_COLS, cp(coa)), "closing-tb.csv": (TB_COLS, x)})
    x = cp(c) + [{"account_number": "9999", "account_name": "Suspense", "account_type": "", "debit": "250.00", "credit": ""}]
    x[0]["debit"] = f"{Decimal(x[0]['debit']) - 250:.2f}"
    case("unmapped-account-in-tb", "GL-016", "a suspense account not in the chart, so the balance sheet doesn't balance", {"chart-of-accounts.csv": (COA_COLS, cp(coa)), "closing-tb.csv": (TB_COLS, x)})
    x = cp(j); first = x[0]["entry_id"]; dup = [dict(r, entry_id="JE-DUP") for r in x if r["entry_id"] == first]
    case("double-posting", "GL-017", "the same deposit entered twice (warning)", full(j_=x + dup))
    with open(os.path.join(OUT, "invalid", "expected.json"), "w", encoding="utf-8") as fh:
        json.dump(cases, fh, indent=2)
        fh.write("\n")


if __name__ == "__main__":
    main()
