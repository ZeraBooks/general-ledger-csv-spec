# General ledger CSV spec

A general ledger in CSV is three files: a chart of accounts (every account with its type and normal balance), a journal (every entry, one row per line, where each entry's debits equal its credits), and a trial balance (every account's balance on a date, where total debits equal total credits). The test that matters is the roll-forward: last month's trial balance plus this month's journal must equal this month's trial balance, account by account. [ZeraBooks](https://www.zerabooks.com/general-ledger-software) is an AI-native general ledger built on that rule: statements become double-entry transactions proven against the bank's printed balances, and every report is calculated from the same ledger.

This repo writes the format down so anyone can use it: JSON Schemas for the three files, 17 rules, six fictional companies with a quarter of books each (510 balanced entries, 24 trial balances), 17 broken file sets, and a Python checker.

- Schemas: [`schema/`](schema/)
- Rules: [`rules/ledger-rules.csv`](rules/ledger-rules.csv)
- Checker: [`cli/gl_check.py`](cli/gl_check.py) (Python 3.8+, standard library)
- Samples: [`samples/`](samples/), all fictional
- Release zip: [latest](https://github.com/ZeraBooks/general-ledger-csv-spec/releases/latest)

## The three files

**Chart of accounts**

```csv
account_number,account_name,account_type,account_subtype,normal_balance,parent_account,active
1000,Operating Checking,asset,bank,debit,,yes
1510,Accumulated Depreciation - Equipment,asset,accumulated_depreciation,credit,,yes
2000,Accounts Payable,liability,accounts_payable,credit,,yes
3100,Owner's Draws,equity,owner_equity,debit,,yes
4000,Bakery Sales,revenue,income,credit,,yes
6100,Rent,expense,operating_expense,debit,,yes
```

Five types: asset, liability, equity, revenue, expense. Assets and expenses are normally debits; the rest are normally credits. Contra accounts (accumulated depreciation, draws, returns and discounts) flip that, and are named so you can tell. Numbering in this spec: 1xxx assets, 2xxx liabilities, 3xxx equity, 4xxx revenue, 5xxx cost of sales, 6xxx-7xxx expenses, 8000-8499 other income, 8500+ other expense.

**Journal**, one row per line (Juniper Lane Bakery's July 15 payroll). Lines that share an `entry_id` are one entry.

```csv
entry_id,date,account_number,account_name,description,debit,credit,entry_type,source,reference
JE-2026-0009,2026-07-15,6000,Wages,Payroll,9708.33,,standard,Payroll report,PR 7/15
JE-2026-0009,2026-07-15,6010,Payroll Taxes,Payroll,742.69,,standard,Payroll report,PR 7/15
JE-2026-0009,2026-07-15,1000,Operating Checking,Payroll,,7572.50,standard,Payroll report,PR 7/15
JE-2026-0009,2026-07-15,2200,Payroll Liabilities,Payroll,,2878.52,standard,Payroll report,PR 7/15
```

Debits 10,451.02 = credits 10,451.02. A line has a debit or a credit, never both, and amounts are always positive. `entry_type` separates standard entries from adjusting, closing, reversing and opening ones; `source` and `reference` say where the entry came from, which is what an auditor asks first.

**Trial balance**

```csv
account_number,account_name,account_type,debit,credit
1000,Operating Checking,asset,36991.73,
2000,Accounts Payable,liability,,1818.85
```

## The rules

| ID | File | Rule |
|---|---|---|
| GL-001 | all | Columns present; amounts positive, two decimals, no symbols |
| GL-002 | chart | Account numbers unique |
| GL-003 | chart | Type is one of the five |
| GL-004 | chart | Normal balance matches the type, unless it's a named contra account (warning) |
| GL-005 | chart | Number in this spec's range for the type (warning) |
| GL-006 | journal | Each entry's debits equal its credits |
| GL-007 | journal | Debit or credit on each line, not both |
| GL-008 | journal | At least two lines and one date per entry |
| GL-009 | journal | Every account is in the chart |
| GL-010 | journal | No postings to inactive or parent accounts (warning) |
| GL-011 | journal | Dates inside the period |
| GL-012 | TB | Total debits equal total credits |
| GL-013 | TB | One side per row, every account in the chart |
| GL-014 | TB | Opening TB + journal = closing TB, per account |
| GL-015 | TB | Balances on their normal side (warning) |
| GL-016 | TB | Assets = liabilities + equity + net income |
| GL-017 | journal | Same date, accounts and amounts twice (warning) |

A trial balance can balance and still be wrong. GL-012 passes if a $10 typo lands on both sides, or if a whole entry is missing. GL-014 is the one that finds those, because it compares every account against what the journal says happened:

```
$ python3 cli/gl_check.py --coa chart-of-accounts.csv --journal journal.csv --opening opening-tb.csv --closing closing-tb.csv
ERROR   GL-006 entry JE-2026-0041: debits 3000.00 vs credits 3010.00 (off by -10.00)
ERROR   GL-014 account 1000: Operating Checking: opening + journal = 36981.73, closing TB shows 36991.73 (off by 10.00)
```

## Run it

```bash
# just the chart
python3 cli/gl_check.py --coa samples/companies/vega-cpa/chart-of-accounts.csv

# a month: chart, journal, opening and closing TB
c=samples/companies/juniper-lane-bakery
python3 cli/gl_check.py --coa $c/chart-of-accounts.csv --journal $c/journal-2026-08.csv \
  --opening $c/tb-2026-07-31.csv --closing $c/tb-2026-08-31.csv --start 2026-08-01 --end 2026-08-31

# build the closing TB yourself from the opening TB and the journal
python3 cli/gl_check.py --coa $c/chart-of-accounts.csv --journal $c/journal-2026-08.csv \
  --opening $c/tb-2026-07-31.csv --build-tb my-tb.csv
```

`--json` prints the result for scripts. Exit code 0 means no errors, 1 means errors, 2 means a file couldn't be read.

## Samples

`scripts/generate_samples.py` writes them from a fixed seed. Every company and number is made up.

Six fictional companies: a bakery, a dental practice, a landscaping company, a freight carrier, a CPA practice and an electrical contractor. Each has a chart of accounts (31 to 32 accounts), an opening trial balance at June 30, 2026 with six months of year-to-date activity, journals for July, August and September 2026, and the trial balance at each month end. The entries are the ones every small business has: weekly deposits (with sales tax for the three that collect it), invoices and customer payments, semi-monthly payroll with withholding, rent, vendor bills and payments, card charges and the card payment, a loan payment split into principal and interest, bank fees, interest earned, owner draws, depreciation, prepaid insurance and inventory count adjustments.

| Folder | What |
|---|---|
| `samples/companies/<company>/` | `chart-of-accounts.csv`, `tb-2026-06-30.csv`, `journal-2026-07.csv` to `-09.csv`, `tb-2026-07-31.csv` to `tb-2026-09-30.csv` |
| `samples/invalid/` | 17 broken file sets, one per rule, with `expected.json` naming the rule and the arguments to run |
| `samples/index.csv` | One row per company per month |

## Where ZeraBooks fits

Keeping a ledger in CSV files is fine for a spec. Keeping your books in them isn't. [ZeraBooks](https://www.zerabooks.com/general-ledger-software) is general ledger software for owners and accountants that keeps these rules for you: every transaction is double entry, every bank and card month is proven against the statement before it's posted, and the trial balance, balance sheet and income statement all come from the same ledger. Its [AI bookkeeping](https://www.zerabooks.com/ai-bookkeeping) categorizes transactions and drafts month-end entries like the depreciation and prepaid lines in these samples for you to review. Moving from other software, it takes your old trial balance as opening balances. One plan covers the ledger and the statement converter: $79 a month billed annually or $149 month to month, with a 7-day trial.

## Tests

```bash
python3 scripts/generate_samples.py
python3 -m unittest discover -s tests -v
```

## License and citation

Code MIT ([`LICENSE`](LICENSE)). Samples, schemas, rules and docs CC BY 4.0 ([`LICENSE-SAMPLES`](LICENSE-SAMPLES)). See [`CITATION.cff`](CITATION.cff). `MANIFEST.json` and `checksums.txt` list every data file with its SHA-256.
