# Daily Log — AI-Power Stack Screener

## 2026-07-22
- Read all 7 design docs; confirmed the mandate: isolate idiosyncratic α+ε vs a commodity ride.
- Scaffolded the workspace to SPEC §10: `docs/` (6 docs), `src/` package skeleton (27 import-light
  stubs — all import clean on Python 3.12), `config.yaml` (validated with pyyaml), `requirements.txt`,
  `.gitignore`, `tests/` stub, `runs/`, `.claude/settings.json`.
- Platform decision: framework-neutral now; UI framework locked at Step 5 (Streamlit vs Reflex).
- Confirmed the `gemini` CLI is ready as the $0 Gate-3 backend (v0.50.0, OAuth done,
  `GOOGLE_CLOUD_PROJECT=gemini-cli-501907`).
- Correlation refinement: 252d **static** correlation = the headline "last-year" number; rolling
  window must be ≪ the sample (default 63d) = the decoupling trajectory only.
- Wired custom commands into `.claude/commands/` (`/compact`, `/concise-answer`, `/pm-review`,
  `/short-code`); **retargeted `/pm-review` + `/short-code`** from the old credit-risk project to this
  one (focus: does the tool find real idiosyncratic alpha and reject commodity riders?).
- Memory: dual setup — in-repo `memory/` (this log + `project-roadmap.md`, the `/compact` target)
  kept in sync with the auto-load `~/.claude` store.
- **Built Step 1 — the regression core**, end to end:
  - `config.py` (Config + load_config + factor-set resolution), `data/prices.py` (yfinance panel,
    per-stock alignment, warm-up for rolling), `regression/engine.py` (OLS → α, betas, idio=α+ε,
    additive cumulatives, compounded headline return), `regression/rolling.py` (static 252d headline
    corr/beta + short rolling), `regression/attribution.py`, `gates/trend.py` (Track tags),
    `viz/charts.py` (Outputs 1–3 + detail table), `main.py` (`run_screen` + CLI).
  - `tests/test_engine.py`: 4 offline correctness tests PASS (recovers α/β; idio=α+ε; Σε≈0 yet
    cum(α+ε)≠0; additive identity; attribution sums).
  - Installed `statsmodels`. Fixed Windows cp1252 console via UTF-8 reconfigure.
  - Smoke-tested on **CEG**: β_oil/β_gas ≈ 0 (expected for nuclear), R²≈0.18, low commodity corr,
    raw −18% / idio −36% → Neutral (de-rating). 5 charts + table render offline in
    `runs/2026-07-22_4factor/`.
- **Built the Streamlit platform shell (Step 5, ahead of gates)** — framework locked to Streamlit
  ("idk what's best, giving to my boss" → chose Streamlit: fastest, hand-off-able, calls run_screen
  directly; Reflex = migration target). Files: `agent/gemini_client.py` (Windows-safe $0 subprocess,
  `cmd /c`, taskkill tree-kill), `app/explain.py` (the "how to read" prompt — explains numbers, never
  invents), `knowledge_base/{hashing,store}.py` (run_id + save/list/load), `viz/figures.py` (per-stock
  Plotly figs), `app/ui.py` (3 pages: New Run / Results / History + per-stock Gemini button).
  - Verified: all modules compile/import; **real gemini call returned in ~26s** (OAuth valid); app
    serves (health ok, HTTP 200); AppTest renders all 3 pages with no exception; full
    run→save→list→reload KB path works. Installed streamlit 1.60; added to requirements.txt.
- **Built Step 2 — gates/ scorecard** (while the app was running for Bryant): `data/market_cap.py`,
  `data/fundamentals/public.py` (best-effort yfinance; null/unverified where unpullable),
  `gates/size.py`, `gates/fundamentals.py` (margin+trend, net debt/EBITDA, EPS surprise, EV/EBITDA
  flag-not-fail). `run_screen` now computes Gates 1-2 for every ticker (scorecard, not funnel);
  new `build_scorecard(result)` = full Output-5 table used by UI + CLI + KB. UI gained a live gate
  strip + per-stock gate detail. Verified on CEG+BE (real data; EV/EBITDA 3yr median correctly shows
  'unverified', not a guess). AppTest green; server restarted on :8501.
- **Built Steps 3 + 4 + Output 4 — all gates now live:**
  - Step 3: `data/fundamentals/refinitiv.py` (reads cached CSV; `.example.csv` template),
    `get_backend()` selector, wired to `fundamentals_source`.
  - Step 4 (Gate 3): `agent/exposure_agent.py`. Discovered the gemini CLI has **no live web search**
    in this env (even with `-y`), so instead of letting it guess I **ground it in real yfinance news**
    (title+summary+URL) and enforce that every cited source ∈ the provided real-URL set — fabricated
    links can't survive. `gates/exposure.py` verdict (pass/flag/fail/pending). Verified on CEG
    (nuclear, aspirational, 3 real-sourced bullets) and VST (merchant_gas, none — under-claimed
    honestly). `gemini_client` gained a `yolo` flag.
  - Output 4: `data/benchmark.py` relative strength vs type benchmark; `figures.fig_relative_strength`;
    shown in the UI once a type is approved. CEG vs XLU = −19.8 pts.
  - UI: full Gate-3 propose-and-approve flow (run agent → sourced bullets w/ verify warning →
    type select → approve/reject → verdict writes back to scorecard G3 → relative-strength chart).
  - Verified: compile, refinitiv/verdict/rel-strength unit checks, AppTest all pages, server restarted.
- **DONE:** all 5 build steps complete. Remaining = polish (real Refinitiv CSV, broader Gate-3 sourcing).

### 2026-07-22 (cont.) — UX round from Bryant's feedback
1. Added the **regression-fit plot** (`figures.fig_regression_fit`): predicted vs actual daily return
   + y=x line + R²/α/βs — "where's the linear regression" answered. New tab per stock.
2. **Tidied the UI**: per-stock charts moved into `st.tabs` (Trend / Regression fit / Decoupling /
   Attribution / Gates & AI exposure) so they stop colliding; metrics row on top.
3. **Gate 3** now returns the agent's **own analyst view** (`comment` field) alongside sourced
   bullets — shown as "🧠 Agent's view". (CEG: "narrative-driven… no contracted deals… not yet secured".)
4. **One return convention**: standardized the whole app on **compounding** for displayed returns +
   chart lines (engine gained `cum_raw_compounded`, `cum_idio_compounded`, `idio_return_compounded`,
   `predicted`; `check_trend` now compounded). Attribution stays additive, labeled "additive breakdown".
   Offline tests still pass (additive identity intact); AppTest green; server restarted.

### 2026-07-22 (cont.) — oil-beta investigation (Bryant flagged CVX)
- Bryant: "CVX shows near-0 oil beta; rolling oil beta looks the same for every company (starts high,
  drops)." Investigated empirically — **NOT an engine bug**: CVX β_oil = +0.22 (p=0.00), oil corr
  +0.56; XOM +0.26/+0.59; CEG ~0 (correct). The −16%/+12% CL=F days are a **real** Mar–Apr 2026 oil-vol
  spike, not bad data.
- Root cause of the confusion: (a) the scorecard didn't DISPLAY betas, so he couldn't see CVX's +0.22;
  (b) rolling beta = cov/var(oil), so when oil's own volatility spiked the shared **denominator**
  shrank every stock's rolling beta together → the common "high then drop" shape (mechanically correct,
  visually misleading).
- Fixes: added **β_market/β_rates/β_oil/β_gas columns to the scorecard**; overlaid the **static 1-yr
  β/ρ as dotted reference lines** on the rolling chart; caption explaining the denominator effect +
  that scorecard betas are multivariate/partial while rolling betas are univariate. No math changed.
- **USO idiosyncratic probe** (Bryant: "USO tracks oil, why isn't β=1 and why +38% idio?"). Computed:
  USO raw +70% vs CL=F factor +26% over the year; daily R²=0.81, corr 0.89, β_oil 0.78. Explained:
  (a) β<1 because of **non-synchronous close** (WTI future settles ~2:30pm ET vs ETF 4pm) + CL=F
  **roll artifacts** → attenuation; (b) the +38% idio is **cumulative divergence** — USO and the CL=F
  continuous series drifted ~44 pts apart (roll/tracking), which the daily beta can't capture, so it
  lands in α+ε. KEY CAVEAT: idiosyncratic can be inflated by factor-tracking noise, not only a real
  own-story; read it alongside R². Open decision (user mid-choice): roll-adjusted crude series vs a
  UI caveat note vs leave. No code changed this turn.

## 2026-07-23 — oil-factor decision RESOLVED + UI redesign (v1.1)
- **Oil-factor decision (was open):** chose **diagnostic + caveat**, NOT a data-source change.
  Rejected FRED spot (changes economic meaning, adds dependency, still not 4pm-synced) and a lagged
  Dimson term (complicates the clean 4-factor model) — the effect is second-order for the real
  power-stack universe (oil betas tiny: CEG≈0, CVX +0.22); the USO +38% was a pure-oil stress test.
  - `gates/trend.py`: `TrendVerdict` gains `tracking_noise` (bool) + `tracking_noise_note`. Flag fires
    when |cum idio| ≥ 20% AND R² ≥ 60% (the USO signature: big own-story sitting on a high R² → likely
    roll/non-sync tracking drift, not genuine alpha). Thresholds = `IDIO_MAGNITUDE_FLAG`, `R2_HIGH`.
    Also a static `OIL_FACTOR_CAVEAT` string (CL=F/NG=F roll + non-sync close). No math changed; the
    diagnostic only WARNS (never fabricates, never drops).
  - `viz/charts.build_scorecard`: appends ` ⚠` to the `idio α+ε` cell when flagged (so it's in the
    saved audit CSV, table width unchanged).
  - `knowledge_base/store`: `meta.json` gains `data_notes` = {oil_factor_caveat, tracking_noise_flagged}
    whenever oil/gas is in the active set — the caveat is preserved in the audit trail.
  - Verified: USO-like (idio +38%, R² .81) flags; CEG-like (R² .18) and big-idio-but-low-R² do NOT.
- **UI redesign (pro-max, applied frontend-design skill):** disciplined research-terminal look.
  - Injected a cohesive CSS token system (`_THEME_CSS`): slate canvas, white cards, indigo→cyan
    "voltage" rule under a hero banner (the signature), **tabular monospace numerals** for all metrics
    + dataframes (financial vernacular, offline-safe — no external fonts/CDN), uppercase eyebrow
    section labels, styled metric cards / sidebar / buttons / expanders / tabs.
  - **Color-coded scorecard** via new `charts.style_scorecard()` (pandas Styler, version-safe .map/
    .applymap): verdict colour = meaning (green pass/Track1, amber flag/Track2, red fail/Reject, slate
    unverified); ⚠ cells amber. Applied on Results AND History (loads saved CSV).
  - Per-stock: **Track pill** badge, tracking-noise `st.warning` + metric delta when flagged, the oil
    caveat under the Trend tab and scorecard when oil/gas active.
  - **Fixed stale text:** Gate-3 strip now shows live `{approved}/{n}` (was "— coming Step 4"); the
    Advanced panel is now LIVE (size floor $B + fundamentals source feed `load_config`, which gained
    `size_floor_usd`/`fundamentals_source` overrides) — dropped the "wired in Step 2/3" disabled stubs.
    Updated the module docstring (all 4 gates live).
  - Verified: py_compile all changed modules; 4 offline tests still pass; AppTest renders New Run /
    Results / History with no exception; styler + diagnostic unit-checked offline. (Pre-existing
    `use_container_width` deprecation warning left as-is — codebase-wide, still functional.)
- **Render fix (Bryant: "not rendered correctly"):** screenshotted the live app via Playwright (it's
  installed) — the CSS applied fine, but Streamlit's NATIVE widgets (primary button, radio, slider,
  checkbox) were still the default coral-red because CSS can't override the theme's `primaryColor`.
  - Fix = added **`.streamlit/config.toml`** `[theme]` (primaryColor #4F46E5 indigo, backgroundColor
    #F6F7F9 canvas, secondaryBackgroundColor #FFFFFF cards, textColor #0F172A). This is the correct
    place for the accent — flows into all widgets. **NOTE: theme changes need a server restart.**
  - The hero "voltage rule" was faint → switched `<hr>` to a `<div class='apx-rule'>` with an explicit
    `linear-gradient(90deg,#4F46E5,#6366F1,#06B6D4)` (no <hr> default-border interference).
  - Added `hide_index=True` to the two styled-scorecard `st.dataframe` calls (Styler's own
    `.hide(axis='index')` isn't honored by st.dataframe; the numeric index 0-4 was showing).
  - Re-verified by Playwright screenshots: New Run button/radio/slider now indigo, gradient renders,
    scorecard color-coding correct (VRT green/Track1, NRG red/fail, amber flags) with no index column,
    combined α+ε chart renders (VRT the clear idiosyncratic winner). All good.

### 2026-07-23 (cont.) — Bryant feedback round 2 (7 comments). Decisions + big build.
- Screenshotted the live app throughout via **Playwright** (installed, Node v24 present).
- **#2 beta "undervalued?" — RESOLVED, not a bug.** CVX univariate daily market β = **−0.40**
  (=TradingView); our scorecard's **−0.10** is the MULTIVARIATE PARTIAL β (after removing oil/gas/
  rates). Gap = simple-vs-partial regression: CVX's oil β (+0.22) + oil↔market correlation shrink the
  partial market β. Proof: CEG (no oil exposure) univariate +1.43 ≈ multivariate +1.35. Added a
  **`simple_market_beta`** property + "mkt β (1y simple)" scorecard column to reconcile with TV.
- **#3 (the core critique: "idio ≈ raw, goes up = idio up") — DONE via alpha significance.** Bryant
  rejected adding a peer FACTOR ("don't want too many factors"). Solution = judge the UNEXPLAINED
  drift statistically, using only the existing factors:
  - engine: `alpha_tstat`, `alpha_pvalue`, `resid_vol_annualized`, `information_ratio`
    (=α_ann/resid_vol_ann; note t-stat ≈ IR), `alpha_significant(p<0.05 & α>0)`, `cum_alpha_drift`.
  - trend: TrendVerdict carries the alpha fields + `alpha_verdict` line + `rank_key` (=IR).
    **Scorecard/per-stock now RANK BY info ratio, not cumulative idio.** New cols: α sig?/α(ann)/
    α t-stat/info ratio. New "🎯 Alpha" tab: `fig_alpha_decomposition` = cum idio (α+ε) vs the pure
    α-drift line → shows steady real alpha vs a jumpy one-off.
  - Verified live: **VRT** raw +139%/idio +47% but α t +0.98, p 0.326 → flagged "alpha NOT
    significant / noise-driven" (amber pill). Exactly the "what's special" answer — separates
    real alpha from "went up." Synthetic test confirms: steady-drift stock (t 5.3) ranks above an
    equal-idio one-off-jump stock (t 1.1).
- **#5 boss regression — matched his literal list (Bryant chose this over my rec).** New **`boss`**
  factor mode = market + WTI(oil) + **Brent (BZ=F)** + Henry Hub(NG=F). Kept NG=F over UNG (roll
  bleed; boss said "Henry Hub OR UNG"). WTI+Brent are ~0.95 collinear → individual betas unstable,
  so added `combined_oil_beta` (β_oil+β_brent, stable) + `BRENT_COLLINEARITY_CAVEAT` shown in boss
  mode. α/R²/idio unaffected by the collinear factor (verified: CEG combined oil β −0.004).
- **Equipment + GEV (#5).** `equipment_tickers` (UI text field) = fundamentals-only, **skipped from
  the regression** (kept out of the price panel); tagged "equipment" in scorecard. `exclude_tickers:
  [GEV]` in config → dropped before any run, surfaced in UI. load_config gained equipment_tickers +
  size_floor_usd + fundamentals_source overrides.
- **#1 chart text collision — FIXED.** All per-stock figs: legends moved to the BOTTOM, titles given
  headroom, redundant rolling-title dropped. **#4 attribution — labels added** (signed pt
  contribution per bar, clean names Market/Rates/Oil/Gas/Own(α+ε)/Total, indigo total). Verified by
  screenshot.
- **DECISIONS LOCKED THIS ROUND:** #3 = alpha-significance (no peer factor); cohort-relative =
  optional sector-grouped lens (TODO); #5 = boss mode (WTI+Brent, NG=F gas, combined oil β);
  platform = **migrate to React/Next.js + FastAPI** (Node v24 confirmed) — pipeline is framework-
  agnostic so analytics carry over; do a PoC first, keep Streamlit as fallback.
- **STILL TODO:** #8 cohort-relative view (Method A, sector-grouped, toggle); #9 KB rework (run
  naming + opt-in "Add to Knowledge Base" + full-result pickle so History re-renders the whole
  dashboard); #10 React/FastAPI migration (+broader look overhaul). Streamlit is the working tool now.

### 2026-07-23 (cont.) — Bryant: "skip #8, build the rest." Did #9 + the React/FastAPI platform.
- **#8 cohort-relative — SKIPPED per Bryant** (may revisit; α-significance already handles the
  general "real vs noise" case without needing a peer group).
- **#9 KB rework — DONE (Streamlit + storage layer).** `store.save_run(result, run_id, name=,
  make_charts=)` now also **pickles the full ScreenResult** (`result.pkl`) + writes `name` into
  meta; `load_full_run()` returns it (try/except → None on cross-version mismatch, falls back to CSV).
  UI: New Run gained a **run-name** field; **auto-save removed** — run_screen(make_charts=False) and
  a **"💾 Add to Knowledge Base"** opt-in button on Results writes meta+csv+pickle+charts. `page_results`
  refactored into a reusable **`render_dashboard(result, run_id)`**; **History** now `load_full_run`
  → re-renders the ENTIRE dashboard (scorecard + combined + per-stock tabs), not just a snapshot.
  Verified: pickle roundtrip, name saved, AppTest re-renders a saved run offline.
- **#10 platform — BUILT a working React/Next.js + FastAPI app (Bryant chose this).** Node v24.
  - **Backend `src/api/`** (framework-agnostic, reuses run_screen): `serialize.screen_payload()` →
    JSON (config, colour scorecard rows, per-stock alpha metrics + series[raw/idio/alphaDrift] +
    attribution + regression-fit + betas, gates, caveats; NaN→null, never fabricated). `server.py`
    FastAPI: `/api/health`, `POST /api/screen` (opt-in save), `/api/history`, `/api/history/{id}`.
    CORS + prod-style. Verified via TestClient (boss mode, equipment skip, history re-open).
    Run: `uvicorn src.api.server:app --port 8000`.
  - **Frontend `web/`** (Next.js 14 app router, JS, npm-installed): design-system `globals.css`
    (verdict colours, tabular-mono, indigo→cyan voltage rule), `lib/api.js` + `lib/format.js`,
    dependency-free SVG `components/LineChart.jsx`, `components/Results.jsx` (gate strip + colour
    scorecard + per-stock cards w/ Alpha/Trend/Regression-fit/Attribution tabs), `app/page.js`
    (New Run / Results / History, opt-in save, history open→re-render). next.config proxies /api/*
    → :8000. Run: `cd web && npm run dev` (:3000). **Screenshotted live — renders great, more
    polished than Streamlit, same analytics.**
  - **React parity NOT yet ported from Streamlit:** Gate-3 Gemini propose-and-approve flow;
    relative-strength (Output 4); rolling-decoupling chart; regression-fit *scatter* (React shows a
    betas table instead); "How to read (ask Gemini)" explainer. Streamlit (:8501) still has these.
- **STATE:** Streamlit app = full features (:8501). React+FastAPI = new polished platform, core +
  alpha-significance complete (:3000 + :8000). All analytics shared in src/. TODO if continuing React:
  port the Gemini Gate-3 flow + the remaining charts; then retire Streamlit.

### 2026-07-23 (cont.) — "Move everything to React; erase history; fresh start." DONE.
- **History erased:** all `runs/<id>/` folders removed (clean slate).
- **React/FastAPI now at FULL PARITY — Streamlit retired (server stopped; `src/app/ui.py` kept as
  reference, deprecated).** Ported everything remaining:
  - Backend endpoints (`src/api/server.py`): `/api/exposure` (Gate-3 agent, Gemini), `/api/exposure/
    verdict` (rules stay in Python), `/api/relative-strength` (Output 4, type→benchmark), `/api/explain`
    (how-to-read), health now returns `geminiAvailable`. `_single_output()` recomputes one ticker's
    StockOutput for explain/rel-strength (stateless). serialize.py gained `headlineCorr` + `rolling`
    (corr/beta series + static refs).
  - Frontend (`web/`): `ScatterChart.jsx` (regression fit); `Results.jsx` now has all 6 tabs — Alpha,
    Trend (+oil caveat), Regression fit (scatter + betas + simple β), Decoupling (rolling corr/beta +
    static dashed refs), Attribution, **Gates & AI exposure** (gate-1/2 detail + full Gate-3 propose-
    and-approve flow: run agent → sourced bullets w/ verify warning → type select → approve/reject →
    verdict + relative-strength chart) + "How to read (ask Gemini)" button. Gemini status in sidebar.
    LineChart gained a `unit` prop (decimals for corr/beta, not just %).
  - **Verified by Playwright screenshots + live API:** all tabs render; scorecard colour-coded; Gate-3
    live call worked (CEG → nuclear/aspirational, 10 real sources, 1 sourced bullet). Decoupling axes
    show proper decimals. Regression-fit scatter + betas render.
- **RUN THE PLATFORM:** backend `uvicorn src.api.server:app --port 8000`; frontend `cd web && npm run
  dev` (:3000, proxies /api → :8000). Open http://localhost:3000.
### 2026-07-23 (cont.) — clarity round (BE confusion).
- Bryant confused by BE's numbers + the Alpha-tab dashed line. Diagnosed: NOT a bug — (a) additive
  (attribution) vs compounded (everything else) convention shown without labels; (b) the compounded
  α-drift overlay exploded [(1+α)^252] AND sat above the real α+ε path due to VOLATILITY DRAG
  (compounding mean-zero noise loses ground) — misleading.
- Fixes (web/ only): **removed the compounded α-drift overlay** — Alpha tab now shows just the
  idiosyncratic (α+ε) curve (= the headline compounded metric), judgement via α t-stat/IR. Added a
  **Glossary** page (④) defining every term + "additive vs compounded" + "why we don't plot compounded
  α". **Legends + captions on every chart** (what each line is). Attribution tab now explicitly
  ADDITIVE, shows each factor's **share of move**, + a callout reconciling compounded-vs-additive (BE:
  raw +760% compounded vs +278% additive). Decoupling tab callout: rolling betas are UNIVARIATE, won't
  match the multivariate partial betas. Metric cards got tooltips. LineChart gained `unit` (decimals
  for corr/beta). Verified live on BE.
### 2026-07-23 (cont.) — beta consistency (Bryant: rolling beta ≠ table; two market betas).
- **ONE beta definition everywhere now.** `regression/rolling.py` gained `rolling_partial_beta` (numpy
  lstsq multivariate OLS per 90d window). main.py uses it (full factor set → show commodity cols), so
  the Decoupling beta chart is the SAME partial-beta as the scorecard. serialize `staticBeta` = the
  model's `reg.betas` (the dashed line now = the exact table value; verified: BE staticBeta oil 0.165 /
  gas 0.013 == table). **Removed the "mkt β (1y simple)" univariate column** (scorecard + serialize +
  fit-tab caption) — no more two competing market betas. Rolling CORRELATION panel stays univariate
  (correlation is a distinct −1..1 concept, only shown there). Glossary + Decoupling callout updated.
  Kept engine.simple_market_beta property (unused, harmless). Tests green; verified via API.
### 2026-07-23 (cont.) — Brent DROPPED (reversal of the earlier "match boss literal" choice).
- Bryant saw BE boss-mode β_oil −0.34 / β_brent +0.60 (opposite signs) — the exact collinearity I'd
  warned about (WTI~Brent corr 0.92; combined +0.26 ≈ WTI-only +0.17; Brent adds ~0 to R²). Shown the
  evidence, he chose **Drop Brent — WTI only**. `FACTOR_SETS['boss'] = ['market','oil','gas']` now.
  brent proxy left in config.yaml but marked UNUSED. combined_oil_beta / BRENT_COLLINEARITY_CAVEAT are
  now dead paths (never trigger) — left in place, harmless. Verified: boss mode = market/oil/gas, BE
  one oil beta +0.20. **Lesson: WTI+Brent together is never worth it — one oil benchmark only.**
### 2026-07-23 (cont.) — fundamentals reliability: yfinance → SEC EDGAR.
- Bryant: "the multiples aren't consistent — where's the data from?" Answer: everything was yfinance
  (Yahoo). Prices/α/β = fine (prices are prices); but Gate-2 MULTIPLES from Yahoo `.info` are patchy /
  mixed-as-of-date / non-standard. No LSEG subscription, so built a **SEC EDGAR backend**
  (`data/fundamentals/edgar.py`) — primary-source filed 10-K financials via data.sec.gov XBRL
  companyfacts (free, no key, credible, current-to-latest-filing). **Now the default**
  (`fundamentals_source: edgar`; get_backend default + API default flipped).
  - Computes EBITDA = OperatingIncomeLoss + D&A (annual FY), margin, YoY, net debt (latest instant
    debt−cash), net debt/EBITDA, last_rev, trailing EV/EBITDA (filed net-debt+EBITDA × LIVE mktcap).
    EPS actual+consensus from yfinance (paired — EDGAR has no analyst consensus). Unresolved tags →
    None/unverified, never fabricated.
  - KEY FIX: `_best_annual` picks the synonym concept with the MOST RECENT annual data — companies
    switch XBRL tags over time (NEE's old 'Revenues' stops 2012; current = RegulatedAndUnregulated...),
    so taking the first-existing grabbed a stale series. Also D&A = Depreciation + intangible amort
    when there's no combined tag (BE). Verified credible on NEE/CEG/VST/ETN/BE (e.g. ETN 1.6x leverage,
    CEG 2.9x, EPS surprises sane); flows into the scorecard via API. Only ev_ebitda_3yr_median +
    rev_consensus stay unverified (historical / vendor-only; both non-critical, flag-only).
  - 'refinitiv' (CSV) + 'public' (yfinance) kept as selectable fallbacks.
- **v1.1 COMPLETE.** All 7 of Bryant's feedback points addressed (only cohort #8 skipped by choice).
  Remaining nice-to-haves: attribution as a waterfall chart in React (currently a table); PNG export;
  real Refinitiv CSV. Consider deleting src/app/ui.py once React is battle-tested.

## 2026-07-24 — Gate-2 flow items switched to TTM (Bryant: "TTM is more relevant than latest 10-K")
- **Rebuilt `data/fundamentals/edgar.py` flow items on a TTM basis.** Root of the earlier "Yahoo vs SEC
  numbers differ" confusion = they measure different things (Yahoo = TTM + its own non-GAAP EBITDA
  recipe + all-in debt incl. leases; our EDGAR = latest FY + OpInc+D&A + LT/current debt). Bryant chose
  TTM. "Check the quarterly filings" → reconstruct each discrete quarter by **differencing consecutive
  YTD facts within a fiscal year** (Q1=3mo, Q2=6mo−3mo, Q3=9mo−6mo, Q4=FY−9mo), sum trailing 4.
  - Only FLOW items change (revenue, operating income, D&A → EBITDA + margins/ratios). Balance sheet
    (net debt) already latest-instant = current; EPS already last-quarter. So TTM leverage + trailing
    EV/EBITDA now match what a PM sees on a screener.
  - Validated line-for-line on real SEC data: **CEG TTM rev = $24.10B** = Q1'26 7.541 + derived Q4'25
    5.694 + Q3'25 5.703 + Q2'25 5.161. CEG EBITDA margin jumps to 33.7% (from FY 25.1%) — REAL, driven
    by a genuine $2.33B Q1'26 operating-income spike FY2025 doesn't see. Exactly why TTM is more relevant.
  - YoY margin now = current TTM margin − year-earlier TTM margin (VST correctly flags −7.0% deteriorating).
- **Two guards added (fix pre-existing bugs, not just TTM):**
  1. **Priority-ordered concept selection** — synonyms tried in list order; ties keep the EARLIER
     (canonical) tag. Fixed CEG's annual denominator (was picking messy `Revenues` → margin 22.3%;
     now clean `RevenueFromContractWithCustomer...`). Applied to both TTM and annual-fallback paths.
  2. **Staleness guard (`STALE_AFTER_DAYS=550`, ~18mo)** — any figure whose latest period is older than
     the window → `unverified`, never reported stale. **Found + fixed a real silent bug: ETN's
     production EBITDA was FY2019 data** (Eaton retired the `OperatingIncomeLoss` tag ~2019; the old
     code used the last value it found and computed "1.6x leverage" against CURRENT net debt). ETN now
     honestly `unverified` — Eaton files no clean operating-income tag recently (only pretax
     `IncomeLossFromContinuingOperationsBeforeIncomeTaxes...`, a DIFFERENT definition — deliberately NOT
     substituted, would reintroduce the "numbers disagree" problem).
- **Basis is labelled + auditable per ticker:** backend returns `basis` ('TTM->2026-03-31' | 'FYxxxx');
  `gates/fundamentals` appends `[basis]` to the EBITDA-margin / net-debt-EBITDA / EV-EBITDA scorecard
  cells; `api/serialize` exposes `fundamentals.basis`. Fallback to latest FY (labelled) when 4 contiguous
  quarters can't be formed.
- Verified: 4 offline tests pass; py_compile clean; full run_screen→screen_payload on CEG+VST OK; TTM
  computes for CEG/NEE/VST/BE/GEV/NRG, honest-unverified for ETN. Fields still None: last_rev_consensus,
  ev_ebitda_3yr_median (historical/vendor-only, flag-only — unchanged).
- **Known coverage limit (follow-up):** tickers that don't tag `OperatingIncomeLoss` (e.g. ETN) get
  EBITDA=unverified. A future interest-inclusive EBITDA path (pretax + interest + D&A, explicit add-back)
  could recover them, but it's a definitional change — deferred, not hacked in.

## 2026-07-25 — Yahoo cross-check on CEG + BE → two more edgar.py fixes; TTM reconciles
- Bryant cross-checked CEG vs Yahoo: rev should be 29.87B (we had 24.10B), net debt ~21.6B (we had 16.56B).
  Both were real bugs, verified against raw filings (not asserted):
  - **Revenue concept:** CEG files `Revenues` (income-statement TOTAL, FY25 25.53B) AND
    `RevenueFromContractWithCustomerExcludingAssessedTax` (ASC-606 subset, 22.66B); ~2.9B/yr gap = non-
    customer revenue (derivative M2M; Q1'26 total 11.12B vs contract 7.54B, both filed). We were using the
    subset → margin inflated (8.13/24.10=33.7%). Operating income is netted from TOTAL revenue, so the
    consistent margin = 8.13/29.87 = **27.2%** (≈ Yahoo 27.6%). Fix: reordered `_REV_SYNS` to prefer
    `Revenues`/`RegulatedAndUnregulated...` (totals) over contract subsets; stale totals (NEE `Revenues`
    stops 2012) excluded by recency so order only breaks ties.
  - **Net debt:** we summed only LTD-noncurrent + current portion − cash, MISSING **ShortTermBorrowings
    5.10B** (CP/revolver @ 2026-03-31). Fix: total debt = LTD-noncurrent + current portion + ST-borrowings
    − cash, with double-count guard (narrow `LongTermDebtCurrent` → add ST separately; broad `DebtCurrent`
    → already bundles ST). CEG net debt → **21.67B** (matches). Operating leases excluded (convention).
- **CEG now ties to Yahoo:** rev 29.87B ✓, net debt 21.67B ✓, margin 27.2% ✓, EBITDA 8.13 vs 8.23B
  (~1.2%, Yahoo non-GAAP normalizations — left as-is, ours auditable). Gate-2 PASS→FLAG (corrected total-
  revenue basis makes margin YoY −0.2%, trips the flag — honest, not a bug).
- **BE (Bloom) cross-check:** rev 2.45B, EBITDA 0.22B (8.8%), net debt 0.12B (0.53x), EV/EBITDA 287x,
  Gate-2 PASS. Net-debt gap vs Yahoo (0.12 vs ~0.46B) = **finance leases** Yahoo includes and we exclude
  (~0.34B) — definitional, small. Mktcap 61.81B = live yfinance ($217.30 × 284.4M sh; AI-power run-up),
  not computed by us; EV/EBITDA 287x correctly flags a hypergrowth name on tiny EBITDA.
- **OPEN for Bryant:** include finance leases in net debt (closer to Yahoo, matters for low-EBITDA names)
  or keep interest-bearing-only (matched CEG)? Leaning keep-excluded. Universe re-validated: CEG/NEE/VST/
  GEV/NRG/BE all compute TTM; ETN honest-unverified. 4 offline tests still pass.

## 2026-07-28 — net debt & EBITDA matched to Yahoo; ETN/GEV recovered; /compact skill upgraded
- Bryant: "match Yahoo Finance; some metrics are unavailable — do the best to extract every data
  correctly." Resolves the 07-25 finance-lease question toward **include** leases.
- Built a live diagnostic harness (scratchpad) comparing `edgar.py` vs yfinance `.info` (= Yahoo) across
  CEG/NEE/VST/NRG/BE/ETN/GEV/VRT, then dumped each filer's actual XBRL debt/cash/income concepts to fix
  with real tags, not guesses. Findings drove the rewrite (never fabricate — hard rule 2).
- **`edgar.py` balance-sheet rewrite → new `_net_debt(facts, fresh)`:**
  - **Finance (capital) leases INCLUDED** (`FinanceLeaseLiability`, or Current+Noncurrent), unless the
    debt concept already bundles them (the `…AndCapitalLeaseObligations` family → guarded, no double-count).
  - **Per-component freshness**: each debt/cash instant must itself be fresh. Fixed the latent bug where a
    fresh short-term component made `max(ends)` pass freshness while a stale long-term component (ETN's
    `LongTermDebtNoncurrent` @2014) silently slipped in → ETN net debt 9.97→**20.59B** (Yahoo 21.08).
  - Long-term debt: prefer fresh `LongTermDebtNoncurrent`(+`LongTermDebtCurrent`); else a total concept
    (`LongTermDebt` / `…IncludingCurrentMaturities` / `…AndCapitalLeaseObligations`). Short-term: umbrella
    `ShortTermBorrowings` if fresh, else `CommercialPaper`+`OtherShortTermBorrowings` → NEE's stale-2019
    umbrella dropped, CP(5.36)+Other(1.26) used → NEE 96.2→**103.5B** (Yahoo 107.3).
  - Cash: `CashAndCashEquivalentsAtCarryingValue`, else `CashCashEquivalentsRestricted…`−`RestrictedCash`
    → **recovered GEV net debt None→−9.83B net cash** (Yahoo −9.00; GEV has neither of the usual tags).
- **Bottom-up EBITDA fallback** (`_flow_ttm` now returns `(now, prev, source)`; new `_PRETAX_SYNS`,
  `_INT_SYNS`): when `OperatingIncomeLoss` is stale/retired, EBITDA = pretax + interest + D&A, labelled
  `(EBIT+D&A)`. Annual path picks op-income else bottom-up, **gated on the latest FY being fresh** (the
  first cut wrongly accepted ETN's stale FY2019 op-income; fixed). ETN EBITDA None→**6.179B** FY2025,
  margin 22.5% ≈ Yahoo 22.2%, nd/EBITDA 3.3x.
- **Verified vs Yahoo:** CEG 21.67/21.60 (unchanged, no lease tag), NRG 23.0/23.2, VRT 0.77/0.76 tie;
  ETN/GEV/NEE fixed as above; VST 18.5→18.75 and BE 0.12 (finance leases only 0.005 — its gap vs Yahoo
  0.46 is **operating leases**, not finance). Residual gaps everywhere = op-leases (excluded by
  convention) + Yahoo non-GAAP EBITDA normalizations. Gate-2 + fundamentals gate render the new
  `FY2025 (EBIT+D&A)` basis label cleanly. 4 offline tests pass.
- **OPEN for Bryant:** include **operating** leases in net debt to fully match Yahoo's headline debt
  (BE/VST/NEE residuals)? Currently excluded (standard net-debt convention). Finance leases now in.
- **`/compact` skill rewritten** (`.claude/commands/compact.md`): now (A) covers everything **since the
  last compact** (reads latest `session-compact-*.md` for the window), caps the handoff at **≤300 words**,
  and (B) **incrementally** updates BOTH memory stores (in-repo `memory/` + the auto-loaded `~/.claude`
  index) so a cold reopen loads full state with no catch-up reading. Merge-not-rewrite; delete stale facts.

### 2026-07-28 (cont.) — vision saved; NEE deep-test; LATEST-FILING fast path built
- Bryant shared a v2 direction (saved to auto-memory [[performance-drivers-vision]], NOT built):
  reframe the platform around a JPM-style **Performance Drivers** panel (`PerformanceDrivers.jpg`) —
  variance decomposition Market/Sector/Macro/Style/Idiosyncratic + per-factor 6M/1Y correlation, with
  Quant-Style factors (Value/Growth/Momentum/LowVol/Quality/Size). Vertical stacked 🔴/🟡/🟢 cards
  (Drivers first, then Fundamentals, then AI-exposure), dropping the "Gate 1/2/3" packaging. Key modeling
  note: use a HIERARCHICAL/orthogonalized decomposition, not one flat collinear OLS. Deferred to scope.
- **NEE deep-test (TTM rev/EBIT/EBITDA/net-profit/net-debt).** Surfaced that our SEC `companyfacts`
  feed LAGS: NEE Q2'26 10-Q was filed 2026-07-24 but companyfacts/companyconcept/frames ALL still ended
  Q1'26 (SEC's aggregated feeds rebuild days-to-weeks behind the raw filing). So we were a quarter behind
  Yahoo through no fault of our reconstruction.
- **FIX — latest-filing fast path in `edgar.py`:** `_facts` now starts from companyfacts, then checks the
  `submissions` index (current on filing) and, for any 10-Q/10-K whose period is newer than the feed
  contains, fetches + parses that filing's XBRL instance (`_htm.xml`) directly and merges it in — only
  non-dimensional (consolidated) us-gaap USD facts. New `_recent_filings`, `_instance_facts`, `_FACTS_CACHE`.
  Extra fetch fires ONLY in-season when a newer filing exists; else no-op. Stays primary-source (reads the
  actual filed document). Validated: NEE rolls to Q2'26 → **revenue 28.701 = Yahoo exactly**, net income
  9.299 = Yahoo exactly, net debt 108.5 vs 107.3 (1%). GEV also advances to Q2; CEG/VST/NRG stay Q1 (no
  Q2 filing yet — correct). 4 offline tests pass.
- **DECISION LOCKED: EBIT = operating income** (`OperatingIncomeLoss`), NOT pretax+interest. Pretax+int
  (Yahoo's "EBIT" row, ~+2.3B on NEE from non-op gains) is used ONLY as the ETN-style fallback when
  operating income isn't tagged. Our EBITDA = op-income + D&A ties to Yahoo's HEADLINE ebitda; Yahoo is
  internally inconsistent (info.ebitda 14.59 vs statement-EBITDA row 17.70).
- **Net-profit finding (for when we add it):** XBRL `NetIncomeLoss` is ALREADY attributable-to-parent
  (NEE 9.299 = Yahoo netIncomeToCommon exactly); consolidated-incl-NCI is `ProfitLoss`. Do NOT subtract
  NCI. Net profit is not yet a REQUIRED_FIELD — add `NetIncomeLoss` directly if Bryant wants it.
- **DECISION LOCKED: latest data = latest OFFICIAL filing (10-Q/10-K) only. NO press-release/8-K path.**
  Bryant: "we don't need press release, just take the latest official filings." Verified all 8 tickers
  reflect their newest filed 10-Q/10-K on EDGAR (NEE/GEV at Q2'26; CEG/VST/NRG/BE/ETN/VRT at Q1'26 because
  that IS their latest filing — they report Q2 early Aug and will roll forward automatically). The only
  fresher source is the earnings 8-K (~2-4wk before the 10-Q) — deliberately NOT used (non-GAAP/unaudited/
  non-standard; violates the auditability rule).
- **Operating income clarified (verified on real filings):** we read the filed `OperatingIncomeLoss`
  line directly whenever a filer reports one (CEG/NEE/VST/GEV/NRG/BE/VRT all do). ETN is the sole
  exception because Eaton's income statement has NO operating-income subtotal line (stops at pre-tax
  income; `OperatingIncomeLoss` last tagged 2019) — hence the bottom-up fallback there, and only there.
- **AAPL test → net-debt cash fix.** AAPL validated the engine: revenue 451.44B, EBITDA 159.98B, net
  profit 122.58B ALL exact to Yahoo; latest filing Q2-FY26 (period 2026-03-28) reflected. Only gap was
  net debt (40.4 vs Yahoo 16.2) — traced to CASH definition: our total debt matched Yahoo to the dollar
  (84.71B), but Yahoo folds **short-term marketable securities** into cash (AAPL 45.57 cash + 22.93 STI =
  68.5) while we counted cash-equivalents only. FIX: `_net_debt` now adds current marketable securities
  (`ShortTermInvestments`/`MarketableSecuritiesCurrent`) to cash — NOT long-term investments (not cash).
  AAPL net debt 40.4→17.4 (≈Yahoo 16.2); every power-stack name UNCHANGED (they tag no STI → no-op). 4
  tests pass. Net-debt convention now: LT debt + current + ST borrowings + finance leases − (cash-equiv +
  short-term investments). Op-leases still excluded (BE 0.12 vs 0.46 residual).
- **BE test.** Revenue 2.449B = Yahoo exact; EBITDA 0.216 vs 0.232; net profit ~breakeven (0.01 vs Yahoo
  0.006) — BE just turned positive (Q4'25/Q1'26). EV/EBITDA 248x (correctly flags rich small-cap). Net
  debt 0.12 vs Yahoo 0.46: entire gap = OPERATING leases (~0.34), which we exclude by convention. OPEN
  (Bryant to decide): include operating leases in net debt to match Yahoo, or keep excluded (my rec —
  standard credit convention, more PM-defensible). Discovery: **BE switched its net-income tag** —
  `NetIncomeLoss` stops 2022, now files `ProfitLoss` — a concrete reason to borrow Joywin's richer tag
  fallback lists when we add a net-profit field.
- **Robustness pass (Bryant: "give latest+accurate financials for ANY company I request; use your
  preference").** Two changes, both re-validated against Yahoo with ZERO regression on the universe +
  AAPL/BE (all still tie):
  1. **Widened the XBRL tag lists** (borrowed from Joywin `sec-financials`), APPENDED as lower-priority
     fallbacks so our Yahoo-matching picks still win: revenue (+services/banks/oil-gas), interest
     (+cash-flow `InterestPaid`), D&A (+oil-gas full-measure), net debt (+`DebtAndCapitalLeaseObligations`,
     `NotesAndLoansPayable`, more short-term + cash variants). `_best_*` picks most-recent-coverage so
     appending is safe. Cash primary list also widened.
  2. **Holdco/reorg CIK fallback.** `company_tickers.json` can map a ticker to a brand-new holding
     company/shell with no financials — found live on **XOM** (maps to 'ExxonMobil Holdings Corp' CIK
     2115436, one 8-K, no XBRL; real filer is 'EXXON MOBIL CORP' CIK 34088). Fix: `_from_edgar` now
     detects a mapped CIK with no recent 10-K/10-Q and falls back to `_ticker_operating_cik` (browse-EDGAR
     Atom, type=10-K) to find the operating filer. XOM went from ALL-BLANK → rev 334B / EBITDA 64B (bottom-
     up, no OperatingIncomeLoss tag) / net debt 34B ≈ Yahoo. Added `_submissions` process cache; `_companyfacts`
     returns {} on 404. Diverse spot-check ok (MSFT/PLD resolve; banks like JPM out of scope — EBITDA/net-debt
     not meaningful for financials). 4 offline tests pass.
- **VRT + GEV validated** (pure test runs, no code change). VRT ties to Yahoo across the board (rev
  10.84B exact, EBITDA 2.32 vs 2.38, net profit 1.56B exact, net debt 0.77 vs 0.76). GEV at Q2'26: rev
  41.37B exact, net profit 9.53B exact, net cash −9.83 vs −9.0. Notable GEV insight: **net profit ($9.5B)
  >> operating income ($1.8B)** — most of GEV's reported profit is NON-operating gains, not the core
  business; our EBITDA (3.0B, operating income + D&A) is the clean operating read vs Yahoo's 3.9B. A good
  "headline profit isn't from operations" signal for the eventual scorecard.

## 2026-07-29 — v2 Performance-Drivers reframe BUILT (Phases 1–3) + rigor + plain wordings + React UI
Scoped the reframe with Bryant, then built it back-to-front over the session. Locked choices up front:
Energy stays its OWN group (mandate); Shapley/LMG for the variance split; ETF proxies via yfinance
(Option A); core engine first, then expand, then UI.
- **Phase 1 — variance engine.** `regression/variance.py`: LMG/Shapley variance decomposition over driver
  groups. Non-negative shares, order-independent, sum to 100%, idiosyncratic = 1 − R². `config.FACTOR_GROUPS`
  + `driver_groups`/`groups_for_factors`. Wired into `run_screen` (per-stock), `api/serialize` (`drivers`
  payload), a horizontal bar chart (`viz/charts.chart_variance_drivers`). **Robust SEs**: `engine.run_regression`
  now fits Newey-West HAC (auto maxlags ~4/yr) — betas/R² identical, only alpha t-stat/p-value change
  (fixes over-optimistic significance from volatility clustering). 7 new offline tests.
- **Phase 2 — full JPM factor set (new `drivers` mode).** Only that mode changed; 4factor/commodity/boss
  untouched. Added Style (IWD/IWF/MTUM/USMV/QUAL, one group), Macro (HYG credit + DBB base metals), and a
  **per-stock Sector factor** (`data/sector.py` → GICS SPDR ETF via override map + yfinance fallback, None
  never faked). `build_return_panel` gained `sector_by_ticker` + robust factor download (a failed ETF is
  dropped + reported in `dropped_factors`, never crashes). `rolling.factor_correlation_table` = 6M/1Y
  univariate corr per factor. `main` derives factor cols from each stock's frame + builds per-stock groups.
  Live-validated drivers mode: CEG sector-driven, VRT style-driven, Energy ~1% for the power stack; CVX =
  Reject with Energy 14% (acid test: the Energy group FIRES for a real oil name). Groups all stable.
- **Rigor round (Bryant "rate it objectively" → ~7.5/10, then fixes to ~9).** (1) **Adjusted R²** in
  `engine` + `variance`: idiosyncratic = 1 − adj R²; LMG shares scaled to adj R² so the explained total is
  df-corrected (relative split unchanged). CEG idio 44.9→47.2% (matched the analytic prediction). (2)
  **Stability check** (`variance.stability`): shares recomputed on the 126d window; groups swinging >10pp
  flagged `unstable`; serialized. (3) **`DRIVERS_MODE_CAVEAT`**: drivers-mode idiosyncratic strips sector+
  style too, so it's stricter than the commodity-only 4factor read. Honest footnotes recorded: adj-R²
  share-scaling is our convention (not a named estimator); Macro proxies directional-only.
- **CVX teaching case (β_oil ≈ 0 puzzle).** Proved empirically: with XLE (energy sector, β 0.93) in the
  model, the partial β_oil collapses to ~0 (XLE absorbs oil) — but oil ALONE explains R² 0.33, and the
  Shapley Energy share (14%) is the fair average over orderings, not the "added-last" β. Why the panel is
  built on Shapley, not raw betas. Univariate oil corr +0.57 unchanged.
- **Plain wordings (Bryant: PM won't get "Track 1/2/Reject").** Verdict labels → "Rising on its own" /
  "Turning up underneath" / "Just riding the wave" / "No clear idiosyncratic trend". Confidence = graded
  tag **Real / Not proven / Likely luck** (t≥2 / 1–2 / <1, `alpha_tier`), not a second competing %. Uses
  "idiosyncratic return", not "own-merit". Updated `trend.py`, `charts._verdict_of`, `web/lib/format.js`,
  `Results.jsx` caption, `Glossary.jsx`. **High-confidence demo:** over 1yr, nothing clears t>2 (elite
  names topped at LLY t 1.21 — 252 daily obs rarely give IR≈2); over 3yr **GE = "Rising on its own / Real"
  (t 2.19, idio +128%, α +31%/yr)**. Lesson: t rewards steadiness over time, not a big number.
- **Phase 3 — React UI.** `web/components/Drivers.jsx` (variance bars + grouped 6M/1Y factor table + 3
  stat cards + stability pill + caveat), wired as the FIRST/default per-stock tab; `drivers` added to the
  factor-mode selector; drivers-mode + dropped-factors banners in `Results`; CSS for bars/grouped table.
  `next build` passes; verified end to end through running servers (`/api/screen` drivers payload carries
  every field the UI reads; sector resolved to "Sector (XLI)" for VRT). Servers stopped at session end.
- **NOT done:** the full vertical-card reframe (dropping the top Gate 1/2/3 strip for stacked 🔴/🟡/🟢
  cards) — Drivers is the primary tab but the gate strip remains. That's the optional next UI step.

## 2026-08-04 — top-down UI rebuild, beta/return fixes, graded AI exposure, financials + Damodaran, DEPLOYED
Big multi-feature window (Bryant iterating toward handing it to his boss). Everything verified live via
Playwright screenshots against the running single-service app.
- **Top-down UI (the vertical-card vision — now DONE).** `web/components/Results.jsx` fully rebuilt:
  ranked summary (click a name) → header band → ① Performance Drivers → ② Size & Risk → ③ Financials →
  ④ AI Exposure → a collapsed **Diagnostics** drawer (regression fit + detailed attribution). The top
  Gate 1/2/3 strip and the per-stock chart tabs are gone. `globals.css` → institutional light
  "research-deck" theme (navy accent, firm corners, tabular numerals). Default factor mode = `drivers`;
  ranked by information ratio.
- **Beta fix (Bryant: "AAPL beta 0.1 is sus").** Header + Size&Risk now show `reg.simple_market_beta`
  (univariate 1-yr), NOT the multivariate PARTIAL beta — in drivers mode the partial market beta inflates
  from collinearity with sector/style (AAPL 0.14 partial vs 0.78 simple; NVDA 4.96 vs 1.88). `engine.py`
  gained `annualized_volatility` + `max_drawdown` for the Size&Risk card. Partial betas live only in the
  Diagnostics regression-fit table, explicitly labelled "partial".
- **Return Bridge (Bryant: "where does the idiosyncratic return come from?").** `Drivers.jsx` shows a
  2-bar bridge: **Raw return vs Own-story (idiosyncratic), both COMPOUNDED** = the exact header numbers.
  Removed all additive numbers from the main view (they didn't reconcile → "which number do I trust");
  the additive per-factor attribution is quarantined in Diagnostics. Rationale: in drivers mode the 12
  collinear factors produce huge offsetting return slices (market +90 / style −92) — useless to show.
- **Risk-vs-return relabel (Bryant: "idio should be 48% × raw").** The 48% is `1−adjR²` = idiosyncratic
  VARIANCE share (risk); the +63% is the idiosyncratic RETURN — different axes, don't multiply. Renamed
  the stat card to "Own share of risk" and the bridge to "Own-story return", with a caption saying so.
- **Removed the Decoupling tab** (confusing) and the **relative-strength "Type" picker** (redundant with
  the regression's idiosyncratic read; it forced you through the AI agent first).
- **Explainer** (`app/explain.py`) rewritten to walk the WHOLE report (verdict/confidence → drivers →
  size&risk → financials → bottom line, one paragraph); fed the gate (size+fundamentals); beta labelling
  fixed (simple = "market beta", multivariate = "partial beta"); compounded-only.
- **AI exposure graded.** `agent/exposure_agent.py` now grades **Strong/Moderate/Low/None** (was
  contracted/aspirational/none) — structural product demand counts, not only signed PPAs (fixes MU
  under-grading). Human approves or overrides the grade; `gates/exposure.py` maps final grade → verdict
  (strong/moderate=pass, low=flag, none=fail). **Gemini web search WORKS** now via `call_gemini(yolo=True)`
  → google_search grounding (the old "no web search in this env" note is STALE). UI: quick news grade
  (~25s) + a "Deep web search (~2min)" button. Verified: MU → Strong with real HBM/Nvidia sources.
- **Gemini dual transport** (`agent/gemini_client.py`): if `GEMINI_API_KEY`/`GOOGLE_API_KEY` set → REST
  API (same gemini-2.5-pro, web search via google_search tool); else local CLI. Enables cloud.
- **Financials additions.** `data/fundamentals/edgar.py` + `base.py` + `gates/fundamentals.py`: net income
  (TTM via `_NI_SYNS` NetIncomeLoss→ProfitLoss, YTD-differenced like rev/EBITDA), `net_income_yoy`,
  `revenue_yoy`, `pe_ratio` (LIVE mktcap ÷ TTM net income). New info rows in the Financials section.
- **Industry benchmark (Damodaran).** `data/industry.py` — REAL Damodaran Jan-2026 averages (EV/EBITDA,
  P/E, EBITDA & net margin) for 16 industries, fetched from pages.stern.nyu.edu (NOT recalled). Each stock
  keyword-mapped from its yfinance industry string → Damodaran industry. `gates/fundamentals.py` compares
  EV/EBITDA + P/E vs the industry avg (flags "rich" if above), appends industry margin context; replaced
  the old "own 3yr median". Source cited in the UI. GOOGL→Software(Internet), NEE→Utility, VST→Power,
  ETN→Electrical Equipment. Unmapped → graceful fallback, never faked.
- **Deployment.** Made it ONE service: `next.config.mjs` `output:'export'` → `web/out`; `api.js` BASE=''
  (same origin); `server.py` mounts `StaticFiles(web/out)`; `web/.env.development` for the dev split.
  Requirements gained fastapi/uvicorn/pydantic. Tried cloud: GitHub repo `bryantt88/ai-power-screener`
  (private) created + pushed; HF Space `bryantt888/ai-power-screener` (public, docker) created — but HF
  free CPU quota = 0 without a card (Render same). User refused card → shipped a **Cloudflare quick
  tunnel** from the PC instead: `cloudflared` installed to `~/bin`, `start-boss-link.bat` at repo root
  starts uvicorn :8000 + the tunnel → a random `*.trycloudflare.com` boss link. GitHub + HF copies are now
  BEHIND the local version. 19/19 tests pass throughout.

## 2026-08-04 — India exit-timing analysis (standalone side deliverable, `india-exit-analysis/`)
Separate task from the screener: find the best exit timing/strategy for the boss's holding in **GS Funds
SICAV – India Equity Portfolio (LU0333810181)**. Built isolated (user: "don't put it in the platform").
Deliverable = both a backtested signal model AND a report. Discipline throughout: never fabricate, latest
data (as-of 2026-07-31), validate every source, defensible to a PM, and DON'T over-anchor on the drivers
method — run a bake-off.
- **Data** (`fetch_data.py`) → 15 daily series to `data/*.csv` (INDA, SMIN, EEM, USDINR=INR=X, BRENT=BZ=F,
  WTI=CL=F, TLT, SPY, NIFTY=^NSEI, DXY, GOLD, ^VIX, ^INDIAVIX, EPI, ^TNX) to 2026-07-31. FII from NSDL
  (GitHub MrChartist/fii-dii-data) → `FII_monthly.csv` (255 months, cross-checked to-the-crore vs Govt PDF).
- **Fund** = near-tracker of MSCI India IMI (USD): beta **0.93**, TE ~4%, bank-heavy (Financials 31%),
  **26% small-cap**, Energy 3%. Trailing yr −12.4%, YTD −7.9%. Proxy **0.74·INDA + 0.26·SMIN** validated
  (`validate_proxy.py`) at **corr 0.988**, 4.6pt error vs fact-sheet yearly returns.
- **Factor scorecard** (`phase1c_factor_table.py`, WEEKLY corr — daily FX is non-sync, a fixed artifact):
  structural (trust always) = EEM +0.69, SPY +0.57, USD/INR −0.47, India VIX −0.44; **oil = regime-flip**
  (6M −0.63 / full +0.07 — positive 79% of history; only trust when recent corr is negative, as now).
- **Backtest** (`phase3_clean.py`, 2013-02→2026-07, 702wk, weekly, signals lagged 1wk, cash=0%, evaluated
  from `df.index[53]` so all signals defined): BuyHold +156%/7.2%/−46%/0.46 · **`Combine_OR` +176%/7.8%/
  −26%/0.59** · `VoteScaled` (phased) +139%/6.7%/−26%/0.55. Combine_OR beats BuyHold on every metric,
  every sub-window; Sharpe 0.52–0.68 across param nudges (not curve-fit).
  - **`Combine_OR`**: exit only when proxy < 200-day AND ≥2 of 4 macro headwinds fire — rupee falling
    >1.5%/13wk · oil rising + regime-on · India VIX > 1yr-70th-pctile · EEM < 200-day. `VoteScaled` scales
    100→66→33→0 as warnings stack.
- **Tested & REJECTED** (honest, not assumed): FII flows *hurt* (Sharpe 0.60→0.47; FII-alone 0.15 — foreign
  selling is coincident/lagging, dumps you at the bottom) · earnings-season · sell-in-May · froth
  (exit-into-strength) · valuation (public P/E stale/gated — needs Refinitiv). **Earnings weeks are NOT more
  volatile**: calendar 0.81–0.94× full/5y/3y/2y, real-earnings-dates 0.98×, latest Jul-2026 week calm.
  "Earnings is a non-factor" — settled a long user thread on whether earnings drive the market (they don't;
  macro does).
- **`phase9_drivers.py`** — platform-style driver decomposition on INDA reusing `src/regression/engine.py`
  + `src/regression/variance.py` (Shapley/LMG), India's OWN factors (SPY/EEM/USDINR/WTI/TLT), weekly.
  FULL: R² 0.56, alpha +23.8%/yr (t+1.45, **ns**), IR +0.85; drivers EM 27% / Global 15% / Rupee 13% /
  Oil 0.4% / **Idio 44%**. Last 2Y: **alpha −33.9%/yr, IR −1.46** (own-story a DRAG). Last 1Y: **Rupee
  17.6% (#1 driver), Oil 13.7% (re-armed from 0.4%), Idio 41.5%**, alpha ns. KEY: **alpha never
  significant, negative last 2yr** → quantifies "alpha-less/negative tracker". (Had a cp1252 print crash on
  the em-dash group name + U+2212 note; fixed by renaming group to "Currency (rupee)" + `PYTHONIOENCODING=utf-8`.)
- **`phase10_volatility.py`** — "is the volatility worth the reward?" INDA vs 11 peer country/region ETFs
  (SPY/EEM/MCHI/EWZ/EWY/EWT/EWW/EZA/EWJ/EWG/EWU), all USD total-return, weekly, fetched fresh. Metrics:
  CAGR, ann vol, Ret/Vol (rf=0), MaxDD, over full/5y/3y/1y. **Finding reframed the question**: India's vol
  (~15–19%) is **mid-pack, even below most peers recently — NOT the problem**. The problem is **reward-per-
  risk is near the bottom**: full-history Ret/Vol **+0.28 (#7/12)**, and **11th/11th/dead-last over 5y/3y/1y**.
  Last 1yr India **−5.5% vs EM-broad +36%** at similar risk; MaxDD −41% full. → the volatility hasn't paid;
  opportunity cost quantified. Dovetails with phase9's negative idiosyncratic return.
- **Report** — `build_report.py` generates `report.html` (research-note CSS + matplotlib charts as base64) →
  `report.pdf` (6pp) via headless Chromium (`scratchpad/html_to_pdf.js`, Playwright `page.pdf` A4). Replaced
  the earlier ugly matplotlib `make_report.py` after user: "the report is so bad… export some pdf skills".
  `MEMO.md` = concise text report (results + backtest + point-form quali + "when to exit"). `FINDINGS.md` =
  full record. `verify_all.py` = single-source-of-truth recompute of every headline number.
- **Strategic thesis** (integrating boss's cost-benefit reasoning): today's signal = HOLD (only 1/5 warnings,
  FII reversing, calm) — BUT the strategic call is a **committed EXIT timed on the drivers**: India is a
  lagging, alpha-less tracker whose ordinary volatility is unrewarded; downside tails (US-India tariffs,
  Iran/oil, EM risk-off, FII) are systematic/un-diversifiable. Not "if" but "when".
- **NEXT:** fold the phase9 driver panel + phase10 peer risk/reward table into `report.pdf` as the two
  "why exit" exhibits (user asked at end of window; awaiting go-ahead).

## 2026-08-05 — India exit reframed to "exit for good"; C1 driver site rebuilt (z-scores + Monte Carlo); C2 catalysts sourced
- **Mandate clarified (boss Steven + Bryant):** the exit is DECIDED — leaving the fund for good. The analysis
  only TIMES the window (benefit-cost / opportunity-cost; India lagged 2-3yr, vol unrewarded, any adverse event
  drags the whole market). Four conclusions: C1 drivers→timing, C2 catalysts, C3 peers, C4 wait-or-go (folded into C2).
- **Data:** refreshed to 2026-08-04; added India-rates driver `INDGILT` (SBI 10yr G-Sec ETF `SETF10GILT.NS`, INR,
  isolates duration, hist from 2016); Brent now primary oil. Every series re-verified vs a fresh live pull (user
  distrust) — all match. SPY "discrepancy" = user saw the S&P500 INDEX (^GSPC ~7736); the model uses the SPY ETF
  (~771 = index÷10). Both correct; site now labels it.
- **C1 rebuilt** (`drivers_analysis.py` → `drivers_output.json`; `build_site.py` + `_theme.css` → `site/index.html`):
  per-driver **z-scores** (level vs 13wk mean/σ — replaces the percentile that a trending driver like USD/INR fools),
  **Composite Macro-Stress Index** (driver z's weighted by Shapley variance share), **block-bootstrap Monte Carlo**
  (10k paths, 13/26wk). Design matches the platform (navy, numbered sections, inline SVG; matplotlib dropped as
  "burem"). Iterated to **decision-first, point-form** per user: SELL verdict + reason bullets on top; **correlation-
  first** driver table (dropped "this week" + CI/p jargon); Macro Composite "sell zone" with data bullets; Monte
  Carlo enlarged full-width with p5/median/p95 + worse/better-off split. **UTF-8 `<meta charset>` fix** (and forced
  utf-8 CSS read) killed mojibake. Served LOCALLY (`open-india-site.bat` → http://localhost:8137), not the Artifact.
- **Method verified** (`recheck_variance.py`): Shapley/LMG is the best driver-breakdown method — independent
  from-scratch LMG matches `drivers_output.json` to the decimal; Johnson Relative-Weights agrees ±1-2pp;
  order-dependent/sequential rejected (SPY 7%↔52% by order); marginal R² double-counts (179%). Weights are
  window-sensitive (oil 25% 1Y → 1% full); user kept 1Y (current regime, oil is a live Iran risk), disclosed.
- **C1 read (as-of 2026-08-04):** stress −0.99σ (calmest ~7% of weeks), fund +1.7σ stretched, all drivers tailwinds
  → **exit into strength now**. Honest caveats: not a called top (fund tends to drift higher short-term when this
  stretched); case rests on asymmetry + opportunity cost, not predicting a fall. Variance (1Y): rupee 15/oil 15/
  global 13/EM 13/rates 3, idio 38%.
- **C2 catalysts (live web search, all sourced):** MSCI review announce **12 Aug** / effective **31 Aug**,
  ~$2.3-3.2B passive inflow IF India weight rises (JM Financial); **RBI held 5.25% neutral** (5 Aug, done);
  **Iran / Strait of Hormuz** = biggest, two-sided tail (Aug-3 US-Iran deal optimism eased oil → why oil z is a
  tailwind now; strait still mostly closed, fragile); **Gen-Z protests** + ~40% graduate unemployment (CNBC), fiscal
  risk is forward (budget still on its 4.3% consolidation path); **Q1 FY27 earnings** soft profits (HDFC Bank rev
  ~−11% YoY, Axis strong); **FII** net −$27.2B YTD but Jun-Jul turned positive ("worst may be over").
- **Wait-or-go (C4) verdict — SELL NOW, don't wait for 12 Aug:** the MSCI money lands 31-Aug, so "waiting for MSCI"
  is a ~3.5-week hold = exactly the window C1 showed has no reliable edge + a real downside tail. The inflow is
  conditional (India's EM weight has been FALLING), mostly priced (estimates public since June), and chases the
  added names (Ather/SAIL), not this bank-heavy fund. Also answered user's "hold into the announcement?" — the
  anticipation premium accrues to candidate stocks, not the broad fund; no fund-level edge measured. Optional
  phased exit: bulk now + one small tranche into any late-Aug MSCI pop.
- **NEXT:** build C2 into the site (catalyst calendar + wait-or-go verdict); optional MSCI-announcement event study; then C3 peer table.
