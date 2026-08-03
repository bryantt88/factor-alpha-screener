## COMPACT — 2026-07-28 (covers since 2026-07-25)

### CHANGED
- Net debt now matches Yahoo: include **finance leases**, per-component freshness, and **short-term investments** in cash (fixed AAPL 40→17B). Operating leases EXCLUDED (industry standard).
- **Bottom-up EBITDA fallback** (pretax+interest+D&A, basis label `(EBIT+D&A)`) for filers that don't tag `OperatingIncomeLoss` — recovers ETN & XOM. EBIT = operating income everywhere else.
- **Latest-filing fast path** (`_facts`): SEC's companyfacts feed lags a fresh 10-Q/10-K by days-to-weeks, so we now merge the newest filing's XBRL instance directly → current to the latest OFFICIAL filing (NEE/GEV at Q2'26). No press-release/8-K path.
- **Holdco/reorg CIK fallback**: `company_tickers.json` mapped XOM to an empty holding-company shell; now when a ticker's CIK has no 10-K/10-Q we resolve the real filer via browse-EDGAR (`_ticker_operating_cik`). XOM went blank→full.
- Widened XBRL tag lists (borrowed from Joywin `sec-financials`), appended as lower-priority fallbacks so Yahoo-matching picks still win.
- GitHub MCP connected (remote server, gh token, user scope) — tools live next session. `/compact` skill rewritten for cumulative memory.

### CODE STATE
- `src/data/fundamentals/edgar.py` — all of the above. Net debt = LT debt + current + ST borrowings + finance leases − (cash + ST investments). `_FACTS_CACHE`/`_SUBMISSIONS_CACHE`.
- Validated vs Yahoo (all tie): AAPL/CEG/NEE/VST/NRG/GEV/VRT/BE + ETN/XOM (bottom-up EBITDA). 4 offline tests pass.

### OPEN / NEXT
1. Scope the **v2 Performance-Drivers reframe** ([[performance-drivers-vision]]) — the big next thing.
- Optional low-risk: add net-profit field (`NetIncomeLoss`→`ProfitLoss` fallback); disk caching + as-of-date backtest (in Joywin repo).

### DECISIONS LOCKED
- EBIT = operating income (pretax+interest only as fallback when untagged).
- Net debt: finance leases in, ST investments in cash, operating leases OUT (standard convention).
- Latest OFFICIAL filing only — no press-release/8-K.
