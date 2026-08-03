# REGRESSION — the math

This is the analytical heart of the tool. Get it exactly right; the user cares deeply about correctness here.

## 1. The model

Daily returns of a stock are regressed on a set of factor returns via OLS:

```
R_stock,t = α + Σ βᵢ · Rᵢ,t + ε_t
```

- `R_stock,t` — the stock's return on day t (what actually happened).
- `βᵢ · Rᵢ,t` — the part of the return explained by factor i (its sensitivity × how much the factor moved).
- `α` — the intercept: the stock's baseline daily drift when all factors are flat.
- `ε_t` — the residual: the daily "surprise" the factors could not explain.

### Two factor modes (user toggle)

| Mode | Model |
|------|-------|
| `4factor` | `R = α + β_mkt·R_SPY + β_rate·R_TLT + β_oil·R_CL + β_gas·R_NG + ε` |
| `commodity` | `R = α + β_oil·R_CL + β_gas·R_NG + ε` |

Factor proxies (daily returns of):
- market → `SPY`
- rates → `TLT` (long Treasuries; TLT up = yields down)
- oil → `CL=F` (WTI front-month future)
- gas → `NG=F` (Henry Hub front-month future)

Use **futures, not ETFs** (UNG/USO decay from contango roll). Never include both WTI and Brent — they are ~0.95 correlated and produce unstable oil betas.

## 2. The key output: idiosyncratic return = α + ε (NOT bare ε)

**This is the single most important convention in the whole tool.**

By OLS construction, the residuals sum to zero over the estimation window: `Σε_t = 0`. So a cumulative-*residual* line is mathematically forced back to 0 at the end — it erases the stock's actual trend. That is wrong and must never be plotted as the result.

The correct quantity is the **idiosyncratic (or "residual") return**, which merges alpha back in:

```
idiosyncratic_t = α + ε_t = R_stock,t − Σ βᵢ · Rᵢ,t
```

i.e. the actual return minus only the factor-explained part. Cumulate it:

```
cumulative_idiosyncratic = Σ_t (α + ε_t)
```

This is the stock's price path **as if every factor had been flat all year** — the precise meaning of the mandate's phrase "bullish trend despite the oil boost." Its slope/endpoint is the Gate-4 pass/fail.

> In code and UI, "residual return" means `α + ε`. Never bare `ε`.

## 3. Raw trend (for the comparison)

The raw trend is the stock's actual performance with nothing removed — the line on any price chart. Build it the same way as the idiosyncratic line, but from actual returns:

```
raw_cumulative_t = Π (1 + R_stock,τ) − 1     for τ = 1..t     (compounded)
```

(For internal consistency with the additive idiosyncratic line you may also present a log/additive cumulative — pick one convention and use it for both lines so the gap is comparable. Recommended: compounded for the headline number, and compute the attribution additively — see §6.)

The **gap between raw and idiosyncratic** = how much of the move the factors explain. This gap is what separates Track 1 (raw up + idio up) from Track 2 (raw down + idio up) from a fake AI play (raw up + idio flat). See SPEC §6.

## 4. Where beta comes from — it is estimated, not looked up

Beta is the slope that best fits the historical cloud of (factor return, stock return) points over the estimation window. You do not fetch it anywhere; the regression computes it from the price data you already pulled.

Single factor (intuition):
```
β = Cov(R_stock, R_factor) / Var(R_factor)
```

Multiple factors (what we actually do): OLS solves them jointly, giving each factor its **partial** beta (its effect holding the others constant):
```
β = (Xᵀ X)⁻¹ Xᵀ Y
```
where `X` = matrix of factor returns (with an intercept column for α) and `Y` = the stock's returns.

In practice:
```python
import statsmodels.api as sm
X = sm.add_constant(factor_returns)      # adds the α (intercept) column
model = sm.OLS(stock_returns, X).fit()
alpha = model.params["const"]
betas = model.params.drop("const")
resid = model.resid                       # ε_t
idio  = alpha + resid                      # α + ε   <-- the quantity we plot
r2    = model.rsquared
pvals = model.pvalues
```

## 5. Estimation window (beta horizon)

Two distinct windows exist — keep them straight:

| Window | Length (default) | Role |
|--------|------------------|------|
| Beta-estimation / residual window | **252 trading days** (static) | Fits one α and one β set over the analysis horizon; produces the primary idiosyncratic line and the scorecard betas. Matches the mandate's "last 1 year." Parameter: `time_horizon`. |
| Rolling-beta window | **90 days**, rolled daily | A *separate diagnostic* — shows whether commodity sensitivity is drifting (the decoupling output). Not the primary residual driver. |
| Robustness re-run | **126 days** (6 months) | Optional sanity check that the 12-month result isn't a window artifact ("last year *or* couple months"). |

**Rule:** the beta window must be `>=` the residual display window for the primary chart. Do not fit β on 90 days and then apply it to 12 months of returns — the early residuals become meaningless. That's exactly why the 90-day rolling beta is kept as its own diagnostic, not used to build the main idiosyncratic line.

Quality/trust metrics to report per stock (not gates): `R²` (how much of the variance the factors explain — low R² on a name means the residual is mostly its own story) and factor `p-values` (whether each beta is real or noise; e.g. oil p-value ≫ 0.05 on a nuclear name is expected and fine).

## 6. Return attribution (feeds the waterfall output)

Over the window, decompose the total return additively:

```
total_return ≈ Σ(α)            (drift)
             + β_mkt · Σ R_SPY  (market slice)
             + β_rate · Σ R_TLT (rates slice)
             + β_oil · Σ R_CL   (oil slice)
             + β_gas · Σ R_NG   (gas slice)
             + Σ ε              (residual surprise; ~0 over the window)
```

The **idiosyncratic slice = Σα + Σε = the α+ε line's endpoint.** Present the market/rates/oil/gas slices as "explained by factors" and the α+ε slice as "the stock's own contribution." This is the single most PM-friendly view: "of this name's +40%, X points were AI/idiosyncratic, Y points were gas, Z the market."

## 7. Worked example (why direction doesn't matter)

Suppose over the window `β_oil = 0.6` for a stock. Oil rises +10%, so the oil-explained return = `0.6 × 10% = +6%`.

| Oil | Stock actual | Oil-explained | Idiosyncratic (actual − explained) | Read |
|-----|-------------|---------------|-----------------------------------|------|
| +10% | +6% | +6% | ~0% | All commodity. **Reject.** |
| +10% | +14% | +6% | +8% | Beat the commodity by a lot. **Screen in.** |
| +10% | +3% | +6% | −3% | Rose, but *lagged* what oil dictated. **Reject** despite looking bullish. |

The regression is direction-agnostic: "oil up, stock up even more" and "oil down, stock up anyway" both yield a positive idiosyncratic return. One formula handles surges and crashes identically.
