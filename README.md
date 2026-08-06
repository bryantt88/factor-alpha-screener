---
title: Factor-Alpha Screener
emoji: ⚡
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Factor-Alpha Screener

A driver-based equity research platform: it decomposes each stock's return into the part explained by
common factors (market, sector, rates, commodities, style, FX…) and the part that is genuinely its
**own story** — the idiosyncratic **α + ε** — then turns that into **actionable, market-neutral trade
ideas** and lets you **backtest** them walk-forward.

> A stock can rise just because the market, its sector, or a commodity rose. We want the return a stock
> earns **beyond what its factor exposures explain** — its own alpha. Strip the factors with a
> regression; what's left (α + ε) is the stock's own trend. Own it, hedge the factors, and you hold the
> alpha.

Works on any liquid market and any set of drivers (US out of the box; Indonesia and fully custom driver
sets built in). Everything is **auditable and reproducible** — every number is computed or sourced,
never fabricated.

---

## The three pillars

### ① Performance Drivers
For each stock, an OLS regression + Shapley variance decomposition answers *"what is actually moving
this stock, and how much is its own story?"* — splitting return variance into driver groups (Market,
Rates, Energy, Style, Sector, Macro…) and the idiosyncratic remainder (`1 − R²`). Reads use
collinearity-robust measures (correlation, grouped variance share) — never raw partial betas.

### ② Trade Ideas
The driver decomposition becomes a threshold-gated shortlist. Every name is categorised —
**Rising on its own** (real, positive own-story alpha) · **Just riding factors** (up, but not its own) ·
**Lagging its factors** (possible mean-reversion) · **No clear edge** — and the platform proposes:
- **Directional longs** — names clearing the alpha-quality bar,
- **Market-neutral pairs** — long a real-alpha name / short a same-factor "rider", matched hedge ratio,
- **Factor-hedged book** — long the names, short factor-proxy ETFs sized to zero the net factor beta.

### ③ Backtesting
A standalone **walk-forward** backtester (strictly no look-ahead) replays the exact live signal at each
rebalance, builds the market-neutral book net of transaction + borrow costs, and reports the equity
curve, **drawdown**, Sharpe, realised market beta, turnover, and more — against buy-hold benchmarks.
Diversification floor, single-name cap, alpha-conviction bar, and rebalance cadence are all tunable;
results save to a local knowledge base.

Plus: **custom / region drivers** (any yfinance ticker), EDGAR fundamentals, and an optional
**AI-exposure agent** (text only, every claim sourced).

---

## Run it locally

The built front-end (`web/out`) is committed, so the whole app runs with **Python alone** — no Node
required for the default path.

**Prerequisites:** Python 3.12+. (Node 18+ only if you want to modify the front-end.)

```bash
git clone <this-repo-url> && cd ai-power-screener

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000
# open http://localhost:8000
```

That serves the full app (UI + `/api`) at one origin. Tabs: **New Run** (score a basket) → **Results**
(ranked read + Trade ideas) → **Backtest** (walk-forward lab) → **History** (saved runs & backtests).

**Command line (no web):**
```bash
python -m src.main --tickers VST CEG NRG VRT ETN --factor-set drivers --horizon 252
```

**Optional AI features** (the AI-exposure agent + the "how to read" explainer):
```bash
# either install the free `gemini` CLI (used as a $0 subprocess), or:
export GEMINI_API_KEY=...           # uses the REST API path (headless / cloud)
```

**Modifying the front-end** (rebuild the static export it serves):
```bash
cd web
npm install
NEXT_PUBLIC_API_BASE= npm run build   # -> web/out (same-origin production build)
```

**Dev mode with hot reload** (two servers):
```bash
python -m uvicorn src.api.server:app --port 8000     # terminal 1
cd web && npm install && npm run dev                 # terminal 2 -> http://localhost:3000
```
(`web/.env.development` points the dev front-end at the :8000 API.)

---

## Configuration

All knobs live in `config.yaml` — market-cap floor, regression windows (risk + signal horizons), factor
proxies, driver groups, leverage flag, benchmark map, fundamentals backend. Nothing is hardcoded in
scattered literals.

## Repository layout

```
src/
  api/            FastAPI server (serves web/out + /api) + JSON serialisation
  config.py       config loader; factor sets, driver groups, custom drivers
  data/           prices, market cap, fundamentals (EDGAR), sector, benchmark, industry
  regression/     OLS engine (α, betas, HAC SEs), rolling stats, attribution, Shapley variance
  gates/          size, fundamentals, trend, exposure
  opportunity/    trade-idea engine (buckets, longs, pairs, factor-hedged book)
  backtest/       vectorised walk-forward market-neutral backtester
  agent/          Gemini client + AI-exposure agent (text only, sourced)
  knowledge_base/ save / load runs and backtests
  viz/            server-side charts
  app/            explain.py — Gemini "how to read" (explains numbers, never invents)
  main.py         CLI + run_screen orchestrator
web/              Next.js front-end (built to web/out, served by FastAPI)
docs/             design specs (regression math, outputs, data, universe)
tests/            pytest suite
config.yaml       all knobs
```

## Testing

```bash
python -m pytest tests/ -q      # offline, no network
```

## Deploy

- **Local shareable link (Windows):** double-click `start-boss-link.bat` — starts the app + a free
  Cloudflare quick tunnel (`*.trycloudflare.com`), no account or card needed.
- **Docker / Hugging Face Space:** the `Dockerfile` runs FastAPI serving `web/out` + `/api` on port
  7860 (the front-matter above configures the Space).
- **Render:** `render.yaml` blueprint (set `GEMINI_API_KEY` as a secret).

## Principles (non-negotiable)

- **Never fabricate a number.** Every market cap, margin, beta, and return is computed or pulled; if it
  can't be, it's marked `null`/`unverified` and surfaced — never guessed.
- **The LLM confirms text, never numbers.** The agent only reads filings/news to confirm exposure, and
  must cite a source for every claim.
- **Idiosyncratic return = α + ε** (never bare residuals), reported as the compounded own-story path.
- **No look-ahead in the backtest** — betas at each rebalance use trailing data only.

## License

Proprietary and confidential — see [LICENSE](LICENSE). All rights reserved.
