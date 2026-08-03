## COMPACT — 2026-07-25

### WHAT CHANGED THIS SESSION
- Root-caused the "Yahoo vs SEC numbers differ" question: definitional (Yahoo=TTM + own non-GAAP EBITDA recipe + all-in debt incl. leases; our EDGAR was latest-FY + contract-revenue subset + partial debt).
- Switched Gate-2 flow items (revenue, OpInc, D&A→EBITDA + margins/ratios) from latest-10K to **TTM**, reconstructed from filed quarters by YTD-differencing (Q1=3mo, Q2=6mo−3mo, Q3=9mo−6mo, Q4=FY−9mo), trailing-4 sum.
- Fixed 4 real bugs surfaced by CEG/BE cross-checks against Yahoo (all in `edgar.py`):
  1. Priority-ordered XBRL concept selection; ties keep earlier (canonical) synonym.
  2. Staleness guard `STALE_AFTER_DAYS=550` → figure older than ~18mo becomes `unverified` (caught ETN silently reporting FY2019 EBITDA).
  3. Revenue concept: prefer `Revenues` (income-statement total) over ASC-606 contract subset → CEG rev 24.10B→**29.87B**, margin 33.7%→**27.2%** (now matches Yahoo 27.6%; consistent with OpInc base).
  4. Net debt: add **ShortTermBorrowings/CP** with double-count guard (narrow LongTermDebtCurrent → add ST separately; broad DebtCurrent → already includes it) → CEG net debt 16.56B→**21.67B** (matches Yahoo ~21.6B).
- Basis labelled per ticker ('TTM->end' | 'FYxxxx'), appended to flow scorecard cells + exposed in API.
- Validated CEG (all 3 numbers tie to Yahoo) and BE (net-debt gap = finance leases, deliberately excluded; mktcap $61.8B is live yfinance AI-run-up; EV/EBITDA 287x correctly flags rich).

### CODE STATE
- `src/data/fundamentals/edgar.py` — REWRITTEN. TTM flow engine (`_duration_single`, `_best_duration`, `_quarter_map` YTD-differencing, `_ttm`, `_da_quarter_map`, `_flow_ttm`); annual fallback (`_best_annual`/`_annual_by_fy` now return `{fy:(val,end)}`); `_latest_instant` returns `(val,end)`; freshness guard; total-debt = LTD-noncurrent + current portion + ST-borrowings − cash; `get_fundamentals` returns `basis`.
- `src/gates/fundamentals.py` — appends `[basis]` to ebitda_margin / net_debt_to_ebitda / valuation notes.
- `src/api/serialize.py` — `_gate_payload` adds `fundamentals.basis` (from `fund_raw`).
- Prototype/validation script: scratchpad `ttm_proto.py` (SEC live-data harness; not in repo).

### CONFIG SNAPSHOT
fundamentals_source = edgar   # default; TTM now primary basis
STALE_AFTER_DAYS = 550        # in edgar.py, not config; ~18mo staleness cutoff

### BACKTEST / RESULTS
None (no regression/backtest run; fundamentals validation only). CEG keystats: rev 29.87B, EBITDA 8.13B (27.2%), net debt 21.67B (2.66x), EV/EBITDA 14.8x, Gate2 FLAG (margin YoY −0.2%). BE: rev 2.45B, EBITDA 0.22B (8.8%), net debt 0.12B, EV/EBITDA 287x, Gate2 PASS.

### BLOCKERS & OPEN QUESTIONS
- **OPEN (user's call): include finance leases in net debt?** Currently excluded (interest-bearing only) — matched CEG. Yahoo includes them; matters for low-EBITDA names (BE 0.53x→~2.1x). Leaning keep-excluded.
- ETN (+ any filer with no clean `OperatingIncomeLoss` tag) → EBITDA `unverified`. Recovering needs an interest-inclusive EBITDA definition (pretax + interest + D&A) — deferred, not hacked.
- EBITDA ~1.2% below Yahoo (8.13 vs 8.23B) = Yahoo non-GAAP normalizations; leave as-is (ours auditable).
- GEV net debt `unverified` (net-cash / debt tags unresolved) — minor.

### NEXT SESSION — DO FIRST
1. Get user's finance-lease decision; if include → add FinanceLeaseLiability{Noncurrent,Current} to the debt sum in `edgar.py`.
2. Optionally spot-check NEE + NRG vs Yahoo (NRG nd/EBITDA 9x — confirm not a debt double-count).
3. Surface `basis` as a clean line in React gate detail (payload already carries it).

### DECISIONS LOCKED
- Gate-2 flow items = TTM (user: "TTM is more relevant"), fall back to latest FY labelled.
- Revenue = `Revenues` total (matches income-statement top line + EBITDA base), not contract subset.
- Net debt currently EXCLUDES leases (pending #1); staleness → unverified, never stale/fabricated.
- Never substitute pretax income for operating income (would reintroduce cross-source disagreement).
