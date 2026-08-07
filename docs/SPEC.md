# SPEC — Factor-Alpha Screener

The complete, current design. This supersedes any earlier exploratory discussion. Where this file and any other disagree, this file wins.

> Note: the platform is now a general factor-model / performance-driver screener for any liquid market; the "power-stack" universe described below is the original built-in preset, not the product's scope.

---

## 1. Purpose

Find mid-to-large-cap, US-listed **AI-power-stack** equities with a genuine, commodity-adjusted AI uptrend. The AI-power stack spans:

- **Power generators** (Bucket 1) — IPPs and utilities that sell electricity: gas, nuclear, renewables, geothermal.
- **Power / data-center equipment** (Bucket 2) — hardware makers: cooling, UPS, switchgear, transformers, turbines, grid gear.

The tool does not pre-commit to a bucket. A ticker is whatever it is; the agent classifies it, the regression treats it appropriately, and the scorecard reports it.

### The core thesis

A power stock can rise simply because oil/gas rose (higher fuel → higher wholesale power price → higher margins). That is a *commodity ride*, not an AI story. We want stocks that rise **by more than commodities (and the market, and rates) can explain**. A rolling OLS regression removes the factor-driven component of returns; the leftover — **alpha + residual (α + ε)** — is the stock's own idiosyncratic trend. A rising cumulative idiosyncratic line = a genuine, structural bid that survives stripping the commodity boost.

See `docs/REGRESSION.md` for the math.

---

## 2. Architecture

A **scorecard pipeline**, not a funnel. Every ticker is run through every gate and scored; nothing is dropped early. Cheap deterministic gates and the expensive regression all run for every name, because a stock can fail the trend gate yet still be a valuable *Track-2 turn candidate* (see §6).

```
Input tickers
   │
   ├─ Gate 1  Size            (deterministic)   ✓/✗ + market cap
   ├─ Gate 2  Fundamentals    (deterministic)   ✓/✗ + metrics
   ├─ Gate 3  AI exposure     (AI agent)        ✓/✗ + sourced summary + type
   └─ Gate 4  Idiosyncratic   (regression)      ✓/✗ + cumulative α+ε trend
                trend
   │
   ▼
Outputs  →  scorecard table + 5 charts   (see docs/OUTPUTS.md)
   │
   ▼
Knowledge base  (save inputs+outputs; dedup by run hash)
```

---

## 3. The gates

### Gate 1 — Size (deterministic)
- **Metric:** market capitalization.
- **Rule:** pass if `market_cap >= size_floor`. Default floor **$2B** (config). Anything below is small-cap and fails.
- Binary. Pure data lookup.

### Gate 2 — Fundamentals (deterministic)
A **lean, decision-relevant** set — not a kitchen sink. Each metric is here because it matters for *this* thesis and is cheaply pullable. See `docs/DATA.md` for sourcing.

| Metric | Definition | Pass rule | Why this one |
|--------|-----------|-----------|--------------|
| EBITDA margin + trend | latest EBITDA margin and YoY change | positive + non-deteriorating | EBITDA beats net income for capital-heavy power names (avoids GAAP-loss false negatives, e.g. leveraged IPPs). Expanding margin = AI-driven pricing power. |
| Net debt / EBITDA | net debt ÷ trailing EBITDA | below a leverage flag (config; producers run higher than equipment) | The one balance-sheet number that actually bites — these are capital-intensive names. |
| Earnings surprise | last-quarter EPS or revenue vs consensus (%) | positive (beat) | Direct read on "beats estimates." |
| Valuation | forward EV/EBITDA vs the stock's **own** 3-yr median | **flag, do not fail** if rich | EV/EBITDA works for GAAP-loss names; vs own history catches "priced for perfection" without a messy peer set. A premium can be justified for a real winner — so flag, don't reject. |

**Deliberately excluded:** P/E (breaks on losses), dividend yield (irrelevant to thesis), standalone revenue growth (backlog matters more — that's the agent's job), current/quick ratios (not what sinks these names). Fewer metrics = fewer API calls + faster runs.

### Gate 3 — AI exposure (AI agent)
The only gate that needs reasoning over unstructured text. See `docs/AGENT.md` behavior below (§7).
- **Output:** short point-form summary of the AI/data-center exposure (signed PPAs, hyperscaler deals, backlog, book-to-bill), **with a source link next to each claim**.
- **Also classifies** the name's type: `merchant_gas | nuclear | regulated | renewable | geothermal | equipment`. This type drives the relative-strength benchmark (§Outputs) and interpretation — it does **not** auto-pick the regression factor set (that's a user toggle).
- **Pass rule:** confirmed, sourced, contracted/quantified AI exposure. Aspirational-only ("exploring", "in talks") → flag as weak, not a clean pass.
- Runs **propose-and-approve**: agent proposes with sources; user approves before it's recorded as a pass.

### Gate 4 — Idiosyncratic uptrend (regression)
The merged trend + residual gate — this is the heart. See `docs/REGRESSION.md`.
- Computes **both** the raw cumulative return and the cumulative idiosyncratic return (α + ε) over the horizon.
- **Pass rule:** positive slope / positive endpoint on the cumulative idiosyncratic line. The raw trend is *measured* but is not its own gate — the gap between raw and idiosyncratic is the diagnostic (Track 1 vs Track 2, §6).

---

## 4. Factor modes

User-selected at the top of each run (a toggle, no auto-switching):

| Mode | Factors stripped | Use |
|------|------------------|-----|
| `4factor` (default) | market (SPY) + rates (TLT) + oil (CL=F) + gas (NG=F) | Cleanest AI signal — removes market beta and rate sensitivity, critical for regulated/renewable names that are rate-driven, not commodity-driven. |
| `commodity` | oil (CL=F) + gas (NG=F) | The literal original mandate. Best for merchant gas/nuclear IPPs where the commodity strip does the real work. |

Whichever mode is chosen, the idiosyncratic return is `α + ε` from that model.

---

## 5. Outputs

Five deliverables, produced on every run, all built to be *read* (annotations, verdicts, tags). Full specs in `docs/OUTPUTS.md`:

1. **Raw vs idiosyncratic trend** — per-stock two-line chart (raw cumulative return vs cumulative α+ε), gap shaded; plus a combined idiosyncratic chart across all tickers for ranking.
2. **Rolling correlation + rolling beta** — 60-day rolling correlation of stock returns vs gas & oil, and 90-day rolling beta — the decoupling view.
3. **Return attribution waterfall** — decomposes each stock's total return into slices: market / rates / oil / gas / idiosyncratic (α+ε).
4. **Relative strength vs sector** — stock vs a type-appropriate benchmark (auto-picked from Gate-3 type).
5. **Scorecard summary table** — one row per ticker; all four gates ✓/✗ with the key number, plus α (annualized), betas, R², factor p-values, raw return (6m + 12m), idiosyncratic return + slope, and the Track tag.

---

## 6. Track 1 / Track 2 (interpreting the raw-vs-idiosyncratic gap)

| Raw trend | Idiosyncratic (α+ε) | Read | Tag |
|-----------|--------------------|------|-----|
| Up | Up | Rising on its own merits — confirmed | **Track 1 — confirmed winner** |
| Down / flat | Up | Price beaten down (sector/rate drag) but the company is strengthening underneath | **Track 2 — turn candidate** |
| Up | Flat / down | Rose only because commodities/market rose — a commodity rider | **Reject — fake AI play** |

Track 2 is the differentiated call: the regression is most useful exactly where price and story disagree. These names *fail the trend gate on raw price* but must still be surfaced.

---

## 7. The AI-exposure agent (Gate 3)

- **Input:** ticker + company name.
- **Job:** (a) confirm AI/data-center exposure from primary sources; (b) classify type.
- **Output format:** point-form bullets, each with a source URL (earnings release, PR, 10-K/10-Q, reputable news). Example:
  - "20-yr PPA with [hyperscaler] for ~X GW nuclear — [link]"
  - "Q_ book-to-bill Y.Yx; backlog +Z% YoY — [link]"
  - Type: `nuclear`
- **Guardrails:** cites everything; produces no financial numbers that belong to Gate 1/2; flags aspirational vs contracted; propose-and-approve before recording a pass.
- **Implementation:** an LLM API + web/news retrieval. Keep the retrieval and the summarization auditable — store the sources with the run.

---

## 8. Knowledge base

Every run is saved as an audit record: **inputs + the outputs as computed at that moment** (so a historical run always shows what it showed then, even after prices move).

**Run identity (dedup hash):**
```
run_id = hash(sorted_tickers + factor_set + return_frequency + time_horizon + as_of_date)
```

- `as_of_date` — the data snapshot. v1: auto-stamped as today. (Keep it a first-class field so backtest can be added later.)
- `time_horizon` — user knob, default 252 trading days (~12 months).
- Change any component → new record. Exact match on all five → **duplicate, blocked** (or points to the existing record).
- Different date, or different horizon, or different factor set = legitimately different knowledge-base entries.

**Storage:** SQLite for the run index + metadata; charts/tables serialized to a run folder (`runs/<run_id>/`). The UI reads the index to list historical runs.

> The website/UI layer — the three pages (New Run, Results Dashboard, History), the top-of-page factor toggle, the propose-and-approve loop, and how dedup is surfaced to the user — is fully specified in `docs/PLATFORM.md`.

---

## 9. Data layer (summary — full detail in docs/DATA.md)

A **source abstraction** so the model doesn't care where a number came from:

- **Prices / returns / market cap** → `yfinance` / public. Free, live, powers the entire regression + all charts + Gate 1.
- **Fundamentals** → swappable backend: `public` (best-effort free, flagged `unverified`) or `refinitiv` (a one-time pull from the boss's terminal, cached to a local CSV/parquet the `refinitiv` backend reads). Identical function signatures — flipping source is a config change.
- **AI exposure** → the agent, live web/news, sourced.

The regression engine depends only on **free public price data**, so the whole core is buildable and testable immediately.

---

## 10. Repo layout

```
ai-power-screener/
├── README.md
├── CLAUDE.md
├── requirements.txt
├── config.yaml                 # floors, defaults, factor proxies, benchmark map
├── docs/
│   ├── SPEC.md
│   ├── REGRESSION.md
│   ├── OUTPUTS.md
│   ├── DATA.md
│   └── UNIVERSE.md
├── src/
│   ├── main.py                 # entrypoint / orchestrator
│   ├── config.py
│   ├── data/
│   │   ├── prices.py           # yfinance price + return pulls
│   │   ├── market_cap.py
│   │   └── fundamentals/
│   │       ├── base.py         # abstract backend interface
│   │       ├── public.py
│   │       └── refinitiv.py    # reads cached Refinitiv file
│   ├── regression/
│   │   ├── engine.py           # OLS, betas, alpha, residuals, idiosyncratic = α+ε
│   │   ├── rolling.py          # rolling beta + rolling correlation
│   │   └── attribution.py      # return decomposition
│   ├── gates/
│   │   ├── size.py
│   │   ├── fundamentals.py
│   │   ├── exposure.py         # calls the agent
│   │   └── trend.py            # wraps regression output into a gate + Track tag
│   ├── agent/
│   │   └── exposure_agent.py
│   ├── viz/
│   │   └── charts.py           # the 5 outputs, annotated
│   ├── knowledge_base/
│   │   ├── store.py            # SQLite index + run folders
│   │   └── hashing.py          # run_id
│   └── app/
│       └── ui.py               # Streamlit platform
└── runs/                       # saved run artifacts
```

---

## 11. Build order

Back-to-front — a working, testable artifact at every step:

1. `regression/` + `viz/` on public prices — the standalone core.
2. `gates/` scorecard.
3. `data/fundamentals/` — `public` then `refinitiv`.
4. `agent/` — Gate 3.
5. `knowledge_base/` + `app/`.
