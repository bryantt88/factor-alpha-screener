# OUTPUTS — the five deliverables

Produced on every run. **Every chart must be built to *read*, not just to plot.** That means: annotated endpoints, a shaded raw-vs-idiosyncratic gap, a one-line plain-language verdict per stock, Track 1 / Track 2 tags, clear legends, and no undecorated spaghetti lines. Prefer interactive (Plotly) so the user can hover for exact values.

Recall the convention: **"idiosyncratic return" / "residual return" always means α + ε**, never bare ε.

---

## 1. Raw vs idiosyncratic trend

**What it shows:** for each stock, two cumulative lines over the horizon — the raw return and the idiosyncratic (α+ε) return — with the gap between them shaded.

**Layout:**
- Per-stock small-multiples grid (one mini panel each) for the detail.
- One combined chart overlaying every stock's idiosyncratic line for ranking at a glance.

**Make it informative:**
- Shade the gap; label it "explained by factors."
- Annotate both endpoints with their values.
- Print the Track tag (Track 1 / Track 2 / reject) and a one-liner: e.g. "Raw +38%, idiosyncratic +9% → mostly a commodity ride."
- Mark the zero line clearly; a rising idiosyncratic line is the pass.

---

## 2. Rolling correlation + rolling beta (decoupling)

**What it shows:** how the stock's relationship to commodities is *changing over time* — the dimension the single 252-day regression averages away.

- 60-day rolling correlation of stock returns vs gas (`NG=F`) and vs oil (`CL=F`).
- 90-day rolling beta to each commodity.

**Make it informative:**
- A falling correlation/beta line = the stock is *decoupling* from commodities → the AI story is taking over. Call that out with an annotation ("decoupling from gas since ~[month]").
- A flat, high line = still a commodity stock.
- Overlay the two commodities on one panel per stock; keep the y-axis fixed to [-1, 1] for correlation so panels are comparable.

---

## 3. Return attribution waterfall

**What it shows:** decomposition of each stock's total return into slices — market / rates / oil / gas / idiosyncratic (α+ε) — per `docs/REGRESSION.md` §6.

**Make it informative:**
- One waterfall (or stacked bar) per stock; a combined grouped bar to compare across names.
- Label the idiosyncratic slice prominently — it's the answer to "how much was actually AI vs commodities."
- Plain-language caption: "Of [ticker]'s +X%, +A came from the market, +B from gas, and +C was idiosyncratic (the stock's own AI/company contribution)."
- Color the idiosyncratic slice distinctly from the factor slices.

---

## 4. Relative strength vs sector

**What it shows:** the stock's cumulative return minus its sector benchmark — the AI premium *above the sector tide*.

**Benchmark auto-picked from the Gate-3 type classification:**

| Type | Benchmark |
|------|-----------|
| merchant_gas / nuclear / regulated | `XLU` (utilities) |
| equipment | `XLI` (industrials) |
| renewable / geothermal | `ICLN` (or `TAN` for solar-heavy) |

(All configurable in `config.yaml` benchmark map.)

**Make it informative:**
- Rising line = beating peers (candidate AI premium); flat = just floating with the sector.
- Annotate the spread at the endpoint ("+25 pts vs XLU").
- This is also the main trend tool for equipment names, where the commodity strip does little.

---

## 5. Scorecard summary table

**What it shows:** the one-glance verdict — one row per ticker.

**Columns:**
- Ticker, company, type
- Gate 1 (size): ✓/✗ + market cap
- Gate 2 (fundamentals): ✓/✗ + EBITDA margin & trend, net debt/EBITDA, last surprise %, EV/EBITDA vs own 3-yr median (with rich-valuation *flag*)
- Gate 3 (AI exposure): ✓/✗ + short note (full sourced bullets in a drill-down)
- Gate 4 (idiosyncratic trend): ✓/✗ + cumulative idiosyncratic return + slope
- Regression detail: α (annualized), each β, R², factor p-values
- Raw return (6m + 12m)
- **Track tag** (Track 1 / Track 2 / reject)

**Make it informative:**
- Sort by cumulative idiosyncratic return by default.
- Color the gate cells (pass/flag/fail); never hide a failing gate — the point is to see *why* a name fails.
- A `null`/`unverified` value must render visibly as such (see hallucination guardrail) — never blank, never guessed.
- One-line verdict per row.

---

## Presentation notes

- Interactive (Plotly) preferred; hover shows exact values.
- Consistent color language across all charts: idiosyncratic/α+ε in one distinct color, each factor in a fixed color, raw price neutral.
- Everything a portfolio manager sees should be defensible cell-by-cell: every number traces to a data pull or a computation, every exposure bullet traces to a source link.
