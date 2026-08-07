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

## Run it on your desktop

The built front-end (`web/out`) is committed, so the whole app runs with **Python alone** — no Node
required. The full app (UI + `/api`) is served at one origin; open **http://localhost:8000**. Tabs:
**New Run** (score a basket) → **Results** (ranked read + Trade ideas) → **Backtest** (walk-forward
lab) → **History** (saved runs & backtests, with delete / clear).

### Easiest — double-click launcher (recommended)

Get the code once, then double-click one file. The launcher creates its own private Python
environment and installs everything on the **first** run, then just starts the app on every run.

1. **Install Python 3.12+** — download from <https://www.python.org/downloads/>.
   On Windows, tick **“Add python.exe to PATH”** during install.
2. **Get the code** — either `git clone <this-repo-url>`, or on GitHub click
   **Code → Download ZIP** and unzip it.
3. **Launch it:**
   - **Windows:** double-click **`run-platform.bat`**
     (first launch: SmartScreen may warn → *More info → Run anyway*).
   - **macOS / Linux:** run `bash run-platform.sh` in a terminal in that folder.
4. Your browser opens **http://localhost:8000** automatically. Keep the launcher window open while
   you use it; close it to stop the app.

That's the whole setup — same experience as the author's machine, no terminal knowledge needed.

### Manual (if you prefer the command line)

**Prerequisites:** Python 3.12+. (Node 18+ only if you want to modify the front-end.)

```bash
git clone <this-repo-url> && cd factor-alpha-screener

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8000
# open http://localhost:8000
```

**Command line (no web):**
```bash
python -m src.main --tickers VST CEG NRG VRT ETN --factor-set drivers --horizon 252
```

### Enable the AI features (optional)

The AI-exposure agent and the "how to read" explainer are the only parts that use an LLM (Gemini).
Everything else works without them — if no key is present, those buttons are simply disabled.

**Each person uses their OWN key** (get a free one at <https://aistudio.google.com/apikey>):

1. Copy **`.env.example`** to **`.env`** in the project folder.
2. Paste your key: `GEMINI_API_KEY=your-key-here`
3. Restart the app.

`.env` is gitignored, so your key stays on your machine and is **never** committed or pushed. (Advanced:
you can instead `export GEMINI_API_KEY=...` in your shell, or install the free `gemini` CLI for a
no-key local login.)

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

## Share it / deploy (optional)

Running it on your own desktop (above) is all most people need. To let *someone else* open it:

- **Temporary shareable link (Windows):** double-click `start-boss-link.bat` — starts the app **and** a
  free Cloudflare quick tunnel (`https://<random>.trycloudflare.com`), no account or card needed. The
  link is live only while the window stays open, and the address changes each launch. Requires
  `cloudflared` on PATH (download the single `.exe` from Cloudflare).
- **Docker / Hugging Face Space:** the `Dockerfile` runs FastAPI serving `web/out` + `/api` on port
  7860 (`docker build -t screener . && docker run -p 8000:7860 screener` → http://localhost:8000).
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
