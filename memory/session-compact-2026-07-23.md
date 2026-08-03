## COMPACT — 2026-07-23

### WHAT CHANGED THIS SESSION
- Oil-factor decision RESOLVED = diagnostic+caveat (tracking-noise flag: |idio|≥20% & R²≥60%); no data change.
- #3 core fix: ALPHA SIGNIFICANCE (α t-stat, p, information ratio) — rank by IR, not raw return. Alpha tab.
- #2: reconciled beta (partial-multivariate vs univariate); rolling beta switched to MULTIVARIATE (matches table); removed the separate "simple market beta".
- #5: `boss` factor mode added then Brent DROPPED (WTI/Brent 0.92 collinear → −0.34/+0.60 split). boss = market+oil+gas.
- Equipment tag (skip regression) + GEV excluded. #4 attribution: % labels + shares.
- #9 KB: run naming + opt-in "Add to Knowledge Base" (no auto-save) + full ScreenResult pickle → History re-renders whole dashboard.
- #10 PLATFORM MIGRATED: Streamlit retired → React/Next.js (`web/`) + FastAPI (`src/api/`). Full parity ported (Gate-3 Gemini flow, charts, glossary). Fixed 500 error = call backend direct (Next proxy times out on slow Gemini).
- Fundamentals: yfinance → SEC EDGAR backend (default). Chart labels + Glossary added. Removed misleading compounded-α drift line.

### CODE STATE
- src/regression/engine.py — α t-stat/p, information_ratio, alpha_significant(), cum_alpha_drift, simple_market_beta (unused).
- src/gates/trend.py — TrendVerdict has alpha fields + rank_key(=IR) + alpha_verdict; OIL_FACTOR_CAVEAT; BRENT_COLLINEARITY_CAVEAT + combined_oil_beta (dead now).
- src/regression/rolling.py — rolling_partial_beta (numpy multivariate OLS per window).
- src/config.py — FACTOR_SETS boss=[market,oil,gas]; exclude_tickers, equipment_tickers; load_config overrides.
- src/data/fundamentals/edgar.py — NEW default backend (SEC XBRL). _best_annual picks most-recent tag; EBITDA=OpInc+D&A (annual); EPS pair + mktcap from yfinance.
- src/data/fundamentals/__init__.py — get_backend default "edgar".
- src/api/{server.py,serialize.py} — FastAPI: /screen /history /exposure /exposure/verdict /relative-strength /explain; JSON payload (α metrics, series, rolling partial beta, gates, caveats).
- web/ — Next.js 14 app: app/page.js (New Run/Results/History/Glossary), components/{Results,LineChart,ScatterChart,Glossary}.jsx, lib/{api,format}.js. api.js calls backend DIRECT (127.0.0.1:8000).
- src/app/ui.py — Streamlit, RETIRED (kept as reference).

### CONFIG SNAPSHOT
fundamentals_source = edgar   # SEC filings default; refinitiv|public fallbacks
factor_set_default = 4factor  # 4factor | commodity | boss(mkt+WTI+gas)
exclude_tickers = [GEV]

### BACKTEST / RESULTS
None run (no point-in-time mode in v1).

### BLOCKERS & OPEN QUESTIONS
- OPEN (user clarifying): computed multiples (EBITDA/net-debt/EV) differ across EVERY source — NEE EBITDA: Yahoo web 17.1B vs yfinance API 14.16B vs EDGAR 14.86B; net debt 92.81/102.41/95.79B. No source agrees (non-GAAP, proprietary adjustments). Only revenue is consistent. Awaiting user's clarification before choosing: keep EDGAR+show-math (recommended) / yfinance-as-is / show-range.

### NEXT SESSION — DO FIRST
1. Resume the multiples question: user wanted to clarify (see BLOCKERS). Likely land on EDGAR + label EBITDA definition + show components (OpInc, D&A, debt, cash) in the Gates tab. Then verify.
2. Restart servers: `uvicorn src.api.server:app --port 8000` + `cd web && npm run dev` → http://localhost:3000.

### DECISIONS LOCKED
- Platform = React/Next.js + FastAPI (Streamlit retired). Pipeline (src/) framework-agnostic.
- Alpha significance (α t-stat/IR) is the "real alpha" test; rank by IR. No peer factor.
- One beta everywhere = multivariate partial. Brent dropped (collinear). boss=mkt+WTI+gas.
- Fundamentals = SEC EDGAR (primary source); computed multiples won't match any vendor — that's inherent, not a bug.
- KB save is opt-in; History re-renders full pickled result.
- No fabricated numbers; unavailable → unverified.
