# DATA — sourcing

Principle: **public-first, deterministic, and auditable.** The regression core depends only on free public price data, so it's fully buildable/testable without any paid feed. Fundamentals use a swappable backend so a one-time Refinitiv pull can slot in without touching any other code.

## Source abstraction

The rest of the model never hardcodes a provider. Three domains:

| Domain | Source | Notes |
|--------|--------|-------|
| Prices / returns | `yfinance` (public) | daily adjusted close → daily returns. Powers the entire regression + all charts. |
| Market cap (Gate 1) | `yfinance` (public) | current shares × price. |
| Factor series | `yfinance` (public) | `SPY`, `TLT`, `CL=F`, `NG=F`. |
| Fundamentals (Gate 2) | swappable: `public` or `refinitiv` | see below. |
| AI exposure (Gate 3) | AI agent + web/news | sourced; see SPEC §7. |

## Fundamentals backend (the swappable part)

Two interchangeable implementations behind one interface (`src/data/fundamentals/base.py`):

### `public` backend (default, v1)
- Best-effort free fundamentals (e.g. via `yfinance` financials, or another free source).
- Fields that are unreliable or missing must be returned as `null` and **flagged `unverified`** — never guessed. The scorecard renders the flag visibly.
- Good enough to build and demo the full pipeline end-to-end.

### `refinitiv` backend (one-time top-up)
- The user's boss can do a **one-time pull** from a Refinitiv/LSEG terminal for the watchlist's fundamental fields (EBITDA & margin history, net debt, EBITDA, consensus estimates & actuals for surprise, forward EV/EBITDA and its 3-yr history).
- Save it as a local file (`data/refinitiv_fundamentals.csv` or `.parquet`).
- The `refinitiv` backend simply **reads that file** — no live API integration, no recurring cost. Re-pull when fresher fundamentals are wanted.
- Same function signatures as `public`, so switching is a one-line config change (`fundamentals_source: refinitiv`).

Required fundamental fields (both backends must return, `null` if unavailable):
```
ebitda_margin, ebitda_margin_yoy, net_debt, ebitda, net_debt_to_ebitda,
last_eps_actual, last_eps_consensus, last_rev_actual, last_rev_consensus,
fwd_ev_ebitda, ev_ebitda_3yr_median
```

## Latest-only (v1)

`as_of_date` is auto-stamped as today; every pull is the latest snapshot. No point-in-time / backtest yet.

**Keep `as_of_date` a first-class parameter anyway** so backtest can be added later without a redesign. When backtest is added:
- prices: slice series to `<= as_of_date` (clean — historical prices aren't revised).
- fundamentals: must become point-in-time (as-reported at that date) to avoid look-ahead bias — this is the hard part and is explicitly deferred.
- agent: restrict to news dated `<= as_of_date`.

## Dependencies (suggested `requirements.txt`)

```
pandas
numpy
statsmodels
yfinance
plotly
streamlit          # UI (later)
pyyaml             # config
```

(Add the LLM/agent client and any web-search/retrieval dependency when Gate 3 is built.)

## Config (`config.yaml`) — the knobs in one place

```yaml
size_floor_usd: 2_000_000_000        # Gate 1
leverage_flag_net_debt_ebitda: 6.0   # Gate 2 producers; equipment stricter
return_frequency: daily
time_horizon_days: 252               # primary beta + residual window
rolling_beta_days: 90                # diagnostic
robustness_horizon_days: 126         # optional 6-month re-run
factor_set_default: 4factor          # 4factor | commodity
fundamentals_source: public          # public | refinitiv
factor_proxies:
  market: SPY
  rates: TLT
  oil: CL=F
  gas: NG=F
benchmark_map:
  merchant_gas: XLU
  nuclear: XLU
  regulated: XLU
  equipment: XLI
  renewable: ICLN
  geothermal: ICLN
```
