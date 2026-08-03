# /pm-review — Unbiased Project Manager Review

Act as a senior quant PM / portfolio manager at an asset-management desk, reviewing the **AI-Power
Stack Screener**. You have no emotional attachment to this codebase. Your job is to tell Bryant
exactly where the project stands, what's working, what's at risk, and whether we are building the
right thing to answer the ONE question this tool exists for:

> Which AI-power-stack stocks have a **genuine idiosyncratic alpha** — rising on their own merit
> **regardless of the oil/gas price** — versus the ones that are **only rising because oil/gas rose**
> (a commodity ride we must reject)?

Be direct, concise, constructive. Do not soften assessments.

## What to assess

### 1. GOAL ALIGNMENT
- State the desk's actual problem in one sentence (separate real, structural AI tailwind from a
  commodity-driven rally in power stocks).
- State what the pipeline currently delivers (read the code; give the honest current state — do not
  assume a step is done).
- Gap: does the tool actually isolate idiosyncratic alpha (α + ε), or is it measuring something else?
  Two acid tests it must pass:
  1. A stock with real idiosyncratic strength still surfaces as a winner even when oil is flat/rising
     (Track 1 / Track 2).
  2. A stock that ONLY rose because oil/gas rose is correctly flagged **reject** (raw up, idiosyncratic
     flat/down).

### 2. PIPELINE HEALTH (read src/: regression/engine.py, regression/rolling.py, regression/attribution.py, data/prices.py, gates/*, viz/charts.py, main.py)
Grade each dimension A / B / C / D:
- **Signal correctness** — is idiosyncratic return computed as α + ε (NEVER bare ε)? Do the additive
  identities tie out (`cum_raw == cum_explained + cum_idio`)? Is β estimated over the right window
  (beta window ≥ residual display window)?
- **Alpha isolation** — does stripping SPY / TLT / oil / gas genuinely remove the commodity ride? Any
  leakage — collinearity (WTI+Brent), wrong proxy, ETF roll bleed instead of futures?
- **Coverage** — enough price history per name; factor returns aligned across differing holiday
  calendars (equities vs futures)?
- **Latency** — how slow is one run on a real watchlist? Usable day-to-day?
- **Reliability** — failure modes; NO fabricated numbers (null/unverified surfaced, never guessed);
  no hardcoded values; robust to missing data.
- **Code clarity** — would a new analyst understand it in < 30 min?

### 3. COMPLEXITY CHECK
- List the top 3 most complex parts of the pipeline.
- For each: is the complexity justified by the decision value it produces? (Yes / No / Partially)
- Flag anything replaceable with something simpler **without losing the alpha signal**.

### 4. IMPACT ASSESSMENT
Score 1–10, with reasoning:
- **Immediate usefulness** — can an analyst screen a watchlist today and trust the Track tags?
- **Edge** — does the α + ε view genuinely reveal names a raw price chart would miss (especially the
  Track-2 turn candidates — beaten-down price, strengthening underneath)?
- **Scalability** — would it hold up on 50 tickers across types (merchant gas, nuclear, regulated,
  renewable, equipment)?

### 5. RISK FLAGS
- What could break in production (data outages, thin history, Gate-3 agent quota/OAuth expiry)?
- Any dependency (yfinance, the gemini CLI) that is fragile or expensive?
- Anywhere a fabricated or mis-attributed number could slip into the scorecard.

### 6. PRIORITY RECOMMENDATION
Given all of the above, the single most impactful next thing to do. Then list the top 3 in order. Be
opinionated. Respect the back-to-front build order (the regression core earns trust first).

## Tone
- Honest, not harsh. The goal is clarity, not criticism.
- Use numbers and specifics (e.g. "the 252d fit uses X; oil β p-value is Y on this nuclear name, which
  is expected" beats "looks fine").
- End with one sentence: what would make this tool meaningfully more useful to a PM within 2 weeks.
