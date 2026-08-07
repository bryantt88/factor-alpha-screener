# CLAUDE.md — Operating Rules

Read this at the start of every session. It is the short, high-signal contract for building this project. Full detail lives in `docs/SPEC.md`.

## What this project is

A screening + regression tool that finds mid-to-large-cap listed equities (any liquid market) with a genuine, factor-adjusted idiosyncratic uptrend. Every ticker runs every gate, gets a scorecard, and the regression isolates the stock's own trend (alpha + residual) from commodity/market/rate noise.

## Hard rules (do not violate)

1. **The LLM confirms text, never numbers.** The agent (Gate 3, AI exposure) is the *only* place an LLM is used. It reads filings/press releases/earnings calls and returns a sourced summary. It must attach a source link to every claim. It must **never** produce a market cap, margin, EPS, beta, or return — those come from data APIs or computation only.
2. **No fabricated figures anywhere.** If a number can't be pulled or computed, mark it `null` / `unverified` and surface that in the output. Never fill a gap with a plausible guess. (The user has been explicit about this — hallucinated financials are the top failure mode to avoid.)
3. **Idiosyncratic / "residual" return = α + ε, always.** Never plot bare residuals ε — by OLS construction Σε = 0, which erases the trend. The decision quantity is the cumulative sum of (α + εₜ). Label it "idiosyncratic return" (or "residual return") in every output and mean α + ε by it.
4. **Two factor modes, user-selected per run:** `4factor` (market + rates + oil + gas) and `commodity` (oil + gas). No auto-switching. It's a top-level toggle.
5. **Latest data only (v1).** As-of date is auto-stamped as today. No backtest / point-in-time mode yet — but keep `as_of_date` as a first-class parameter so backtest can be added later without a redesign.
6. **Scorecard, not funnel.** Do not pre-drop tickers. Run every gate on every ticker, flag ✓/✗ with the underlying number, run the regression on all of them (Track-2 turn candidates fail the trend gate but must still be computed).

## Conventions

- **Language / stack:** Python. `pandas`, `numpy`, `statsmodels` (OLS), `yfinance` (prices), `plotly` or `matplotlib` (charts), `streamlit` (UI, later), `sqlite` (knowledge base).
- **Factor proxies:** market = `SPY`, rates = `TLT`, gas = `NG=F` (Henry Hub front-month future), oil = `CL=F` (WTI front-month future). Use **futures, not the ETFs** (UNG/USO bleed from roll). Never put WTI and Brent in the same model (collinear).
- **Returns:** daily by default (frequency is a parameter).
- **Beta window:** 252 trading days (static) by default; a parameter. Rolling 90-day beta is a *separate diagnostic output*, not the primary residual driver.
- **Config over hardcoding:** market-cap floor ($2B default), horizon (252d default), factor set, frequency, benchmark map — all live in a config, not scattered literals.
- **Modular repo** (see `docs/SPEC.md` §Repo layout): `data/`, `regression/`, `gates/`, `agent/`, `knowledge_base/`, `viz/`, `app/`. Not one giant script.
- **Every output must be built to *read*** — annotated endpoints, shaded raw-vs-idiosyncratic gap, a one-line plain-language verdict per stock, Track 1 / Track 2 tags. See `docs/OUTPUTS.md`.

## Build order

Back-to-front, so there's a working, testable artifact at every step:
1. `regression/` engine + its charts, on public price data (no fundamentals, no agent needed).
2. `gates/` scorecard around it.
3. `data/` fundamentals backend — `public` first, `refinitiv` (cached file) swappable.
4. `agent/` Gate-3 exposure agent — propose-and-approve, sourced.
5. `knowledge_base/` + `app/` UI.

## When in doubt

Prefer the version that is auditable and reproducible over the one that is clever. This tool's value is that a human can trust and defend every cell of the scorecard to a portfolio manager.

## Project memory (read at session start)

Persistent context lives in `memory/` in this repo — read it first each session:
- `memory/project-roadmap.md` — goal, build order + status, decisions locked, next actions.
- `memory/daily-log.md` — dated session log; the most recent entry is where we left off.
- `memory/session-compact-<date>.md` — per-session handoffs written by `/compact`.

Custom commands live in `.claude/commands/`: `/compact` (session handoff → `memory/`), `/concise-answer`, `/pm-review` (PM review of *this* screener), `/short-code`. Claude Code also keeps an auto-loaded memory index outside the repo that mirrors these facts.
