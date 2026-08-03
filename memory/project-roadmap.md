# Project Roadmap — AI-Power Stack Screener

**Goal (one sentence):** find US-listed AI-power-stack stocks with genuine **idiosyncratic alpha** —
rising on their own merit **regardless of oil/gas prices** — and reject the ones that only rose
**because** oil/gas rose (a commodity ride).

## The decision the tool must get right
- Isolate **idiosyncratic return = α + ε** (never bare ε) by stripping market/rates/oil/gas via OLS.
- **Track 1** (raw up + idio up) = confirmed winner; **Track 2** (raw down + idio up) = turn
  candidate; **Reject** (raw up + idio flat/down) = commodity rider / fake AI play.
- Two acid tests: (1) a name with real idiosyncratic strength surfaces even if oil is flat/up;
  (2) a name that ONLY rose with oil/gas is flagged reject.

## Build order & status
1. [x] **regression/ + viz/** — Step 1 **DONE (2026-07-22)**. OLS engine (α, betas, idio=α+ε),
   static+rolling corr/beta, additive attribution, Track tags, 5 Plotly charts + detail table, CLI
   (`run_screen`), 4 passing offline correctness tests. Smoke-tested on CEG.
2. [x] gates/ scorecard — Step 2 **DONE (2026-07-22)**: `gates/size.py` + `gates/fundamentals.py` +
   `data/{market_cap,fundamentals/public}.py`; full Output-5 scorecard (`build_scorecard`) wired into
   UI (live gate strip + per-stock gate detail), CLI, and KB. Public fundamentals return null/unverified
   where unpullable — surfaced, never guessed.
3. [x] data/fundamentals refinitiv backend — Step 3 **DONE (2026-07-22)**: `refinitiv.py` reads a
   cached CSV (`data/refinitiv_fundamentals.csv`; see `.example.csv`); `get_backend(source)` selector;
   `fundamentals_source: refinitiv` switch. Fills the fields public can't verify.
4. [x] agent/ Gate-3 exposure — Step 4 **DONE (2026-07-22)**: `exposure_agent.py` grounded in REAL
   yfinance news (gemini has no live web here → the model may cite ONLY provided news URLs, enforced
   in code, so no fabricated links). `gates/exposure.py` verdict; propose-and-approve UI; **Output 4
   relative-strength vs type benchmark** (`data/benchmark.py`) shown on approval. ALL FOUR GATES LIVE.
5. [~] knowledge_base/ + app/ UI — **platform shell DONE (2026-07-22, Streamlit)**: 3-page app
   (New Run / Results / History), per-stock "How to read (ask Gemini)" button, KB save/load
   (runs/<run_id>/ + meta.json + scorecard.csv). Gates 2–4 wire into its existing sections next.
   Launch: `streamlit run src/app/ui.py`.

**Done:** workspace scaffolded to SPEC §10; Step 1 regression core implemented, tested, and
smoke-run. `python -m src.main --tickers CEG --factor-set 4factor --horizon 252` produces charts +
a ranked detail table in `runs/<as_of>_<factor_set>/`.

## Decisions locked (do not revisit without reason)
- Idiosyncratic = α + ε. **User-facing convention = COMPOUNDING** for every displayed return and all
  chart lines (chosen 2026-07-22 — user found the additive/compounded mix confusing). Additive
  cumulatives are kept ONLY for the attribution breakdown (the one place slices must sum linearly),
  clearly labeled "additive breakdown". engine exposes both: `cum_*_compounded` (display) +
  `cum_*` additive (attribution) + `predicted` (for the regression-fit plot).
- Correlation: **252d STATIC** = headline "how correlated over the last year"; **rolling window ≪
  sample** (63d) = decoupling-trajectory diagnostic only. Never a 252d rolling window on a 252d sample.
- Factor modes user-toggled (4factor default | commodity); **futures not ETFs**; never WTI+Brent.
- **Never fabricate numbers** → null/unverified. LLM confirms **text only** (Gate 3).
- UI framework **MIGRATED to React/Next.js + FastAPI** (2026-07-23; superseded the original Streamlit
  choice). Backend `src/api/` (FastAPI wraps run_screen → JSON); frontend `web/` (Next.js 14). Streamlit
  (`src/app/ui.py`) retired but kept as reference. Pipeline (src/) stays framework-agnostic — the API
  and Streamlit both call the same run_screen. Run: `uvicorn src.api.server:app --port 8000` + `cd web
  && npm run dev` → http://localhost:3000.
- Gemini "how to read" button = optional, on-demand explainer via `src/app/explain.py` +
  `src/agent/gemini_client.py`. LLM only EXPLAINS computed numbers, never invents them.
- Gate-3 agent = gemini CLI $0 subprocess (GCP project `gemini-cli-501907`), paid HTTP fallback rung.

## Status: v2 Performance-Drivers Phases 1–3 BUILT (2026-07-29) — JPM-style variance panel live end to end.
Platform: `uvicorn src.api.server:app --port 8000` + `cd web && npm run dev` → http://localhost:3000.
v1.1 base still intact (React/FastAPI, all 7 Bryant pts, Gate-2 TTM Yahoo-matched, alpha-significance,
boss mode, EDGAR fundamentals, opt-in KB, Glossary). NEW this session — a `drivers` factor mode that
renders a Shapley/LMG variance decomposition (Market/Rates/Energy/Sector/Style/Macro/Idiosyncratic,
sums to 100%) + a 6M/1Y factor-correlation table, as the first/default per-stock tab. 19/19 tests pass.

- **v2 Performance-Drivers reframe — Phases 1–3 DONE (2026-07-29).** `regression/variance.py` (Shapley/LMG,
  idiosyncratic = 1 − adjusted R²); new `drivers` mode (config.py `FACTOR_SETS`/`FACTOR_GROUPS`,
  `driver_groups`); per-stock Sector factor (`data/sector.py`, GICS→SPDR ETF); rigor upgrades in
  `engine.py` (Newey-West HAC SEs; adjusted R²) + a 6M-vs-1Y stability check; React `web/components/Drivers.jsx`
  (bars + factor table, first tab). Validated live: CEG sector-driven, VRT style-driven, Energy ~1% (no
  commodity ride); CVX = Reject/Energy 14%; GE 3yr = "Real" (t 2.19). See daily-log 2026-07-29.
- **Wordings simplified (2026-07-29):** verdict labels are plain ("Rising on its own" / "Turning up
  underneath" / "Just riding the wave" / "No clear idiosyncratic trend", was Track 1/2/Reject/Neutral);
  confidence tag = Real / Not proven / Likely luck (t≥2 / 1–2 / <1). Uses "idiosyncratic return".
- **RESOLVED (2026-07-28) — financials extraction is Yahoo-accurate AND current to the latest official
  filing.** `edgar.py` reworked: (1) net debt = LT debt + current + ST borrowings + **finance leases** −
  (**cash + short-term investments**), per-component freshness; operating leases EXCLUDED (industry-
  standard convention — LOCKED). (2) **Bottom-up EBITDA** (pretax+interest+D&A, labelled `(EBIT+D&A)`)
  when a filer doesn't tag `OperatingIncomeLoss` (ETN, XOM); EBIT = operating income otherwise (LOCKED).
  (3) **Latest-filing fast path** — companyfacts lags fresh filings by days-to-weeks, so we merge the
  newest 10-Q/10-K XBRL instance directly → current to the latest OFFICIAL filing (no 8-K/press release).
  (4) **Holdco/reorg CIK fallback** — resolves the real 10-K filer when `company_tickers.json` points a
  ticker at an empty shell (found on XOM). (5) Widened XBRL tag lists (Joywin borrow, appended as
  fallbacks). Validated vs Yahoo, all tie: AAPL/CEG/NEE/VST/NRG/GEV/VRT/BE + ETN/XOM. 4 offline tests
  pass. See session-compact-2026-07-28 + daily-log 2026-07-28.
- **NEXT (optional): full vertical-card UI reframe.** Phases 1–3 built the analytics + a Drivers panel as
  the primary per-stock tab, but the top-level Gate 1/2/3 scorecard strip is still present. The vision's
  full restructure — drop the gate packaging, stack vertical 🔴/🟡/🟢 cards (Drivers → Fundamentals →
  AI-exposure) — is a further UI-only step, not yet done. See memory `performance-drivers-vision`.
- **Locked v2 modeling choices:** Energy AND Rates each kept as their OWN group (not folded into Macro like
  JPM); Macro = HYG(credit) + DBB(base metals), single ETFs, directional-only (FRED/breakeven deferred);
  idiosyncratic = 1 − adjusted R² with LMG shares scaled to adj R² (relative split unchanged); Style = 5
  ETFs (IWD/IWF/MTUM/USMV/QUAL) entered together, reported as one Style group; ETF proxies via yfinance
  (Option A), backend swappable later. Drivers mode is a user toggle — 4factor/commodity/boss unchanged.
- **RESOLVED (2026-07-24/25) — "multiples disagree across sources":** the gap was definitional (Yahoo=TTM
  + own non-GAAP recipe + all-in debt incl. leases; our EDGAR was latest-FY + contract-revenue subset +
  partial debt). Gate-2 flow items (rev/OpInc/D&A→EBITDA + margins/ratios) now computed **TTM** from filed
  quarters (YTD-differencing; Q4=FY−9mo), basis labelled per ticker ('TTM->end' | 'FYxxxx'). Balance sheet
  stays latest-instant. Fixed 4 latent `edgar.py` bugs (all verified vs raw filings + Yahoo on CEG/BE):
  (1) priority-ordered XBRL concept selection; (2) staleness guard `STALE_AFTER_DAYS=550` (ETN was
  silently reporting FY2019 EBITDA → now unverified); (3) revenue = `Revenues` total not ASC-606 subset
  (CEG rev 24.10→29.87B, margin 33.7→27.2% ≈ Yahoo); (4) net debt adds ShortTermBorrowings (CEG 16.56→
  21.67B ≈ Yahoo). CEG now ties to Yahoo on all 3. **OPEN:** include finance leases in net debt? (BE gap
  = leases; Bryant to decide, leaning exclude.) See daily-log 2026-07-24 + 07-25, session-compact-07-25.

## Remaining (polish / v1.1, not blockers)
- **Oil factor quality — RESOLVED (2026-07-23): diagnostic + caveat.** Kept CL=F/NG=F (no data-source
  change; futures per hard rule). Added a per-stock tracking-noise flag (|cum idio|≥20% AND R²≥60% →
  ⚠) + `OIL_FACTOR_CAVEAT`, surfaced in the scorecard/UI and saved to the audit trail (`meta.json`
  `data_notes`). Rejected FRED-spot (changes meaning, adds dep) and a lagged Dimson term (complicates
  the model) — effect is second-order for the real universe. See daily-log 2026-07-23.
- **UI redesign — DONE (2026-07-23):** research-terminal design system (CSS tokens, tabular-mono
  numerals, color-coded scorecard via `charts.style_scorecard`, hero banner, live gate strip, live
  Advanced panel). Stale "coming Step X" text removed.
- Get the boss's real Refinitiv CSV into `data/refinitiv_fundamentals.csv` (fills unverified fields).
- Gate-3 coverage is limited to what's in recent yfinance news (no live web search here). If a paid
  search/HTTP LLM rung is added, wire it as the escalation rung to broaden sourcing.
- Optional: colour the scorecard gate cells in the UI; robustness re-run (126d); PNG export (kaleido).
- Consider a "Run Gate 3 for all tickers" batch button (currently per-stock).

## Step-1 notes worth keeping
- At horizon=252, `α (ann.)` == `idio α+ε (cum)` by construction (Σε=0, 252 obs) — a consistency check.
- CEG (nuclear) validated the model: β_oil/β_gas ≈ 0 (expected), R²≈0.18 (own-story dominates),
  low commodity correlation. Charts render offline (local plotly.min.js).
- Windows console is cp1252 → `main._ensure_utf8_stdout()` reconfigures stdout for α/ε/² glyphs.
