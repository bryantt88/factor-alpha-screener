"""Offline correctness proof for the regression engine (no network).

The auditable heart-check (docs/REGRESSION.md): synthesize returns with KNOWN alpha/betas + noise,
then assert the engine recovers them and that the alpha+epsilon conventions hold:
  - recovered alpha, betas ~= truth
  - identity: cum_raw_additive == cum_explained + cum_idio
  - sum(epsilon) ~= 0 over the window, yet cum(alpha+epsilon) is NOT forced to 0 (why we plot alpha+eps)
  - attribution slices sum to the additive raw endpoint
"""
import numpy as np
import pandas as pd

from src.regression.attribution import attribution
from src.regression.engine import run_regression

TRUE_ALPHA = 0.0006
TRUE_BETAS = {"market": 1.10, "rates": -0.30, "oil": 0.20, "gas": 0.55}
N = 600
NOISE_SD = 0.005


def _synthesize():
    rng = np.random.default_rng(42)
    idx = pd.date_range("2024-01-01", periods=N, freq="B")
    factors = pd.DataFrame(
        {name: rng.normal(0.0, 0.011, N) for name in TRUE_BETAS}, index=idx
    )
    eps = rng.normal(0.0, NOISE_SD, N)
    stock = TRUE_ALPHA + sum(TRUE_BETAS[f] * factors[f] for f in TRUE_BETAS) + eps
    return pd.Series(stock, index=idx, name="TEST"), factors


def test_engine_recovers_known_params():
    stock, factors = _synthesize()
    r = run_regression(stock, factors)

    assert abs(r.alpha - TRUE_ALPHA) < 1e-3, (r.alpha, TRUE_ALPHA)
    for f, b in TRUE_BETAS.items():
        assert abs(r.betas[f] - b) < 0.05, (f, r.betas[f], b)


def test_idiosyncratic_is_alpha_plus_epsilon_not_bare_epsilon():
    stock, factors = _synthesize()
    r = run_regression(stock, factors)

    # idio == alpha + residual, exactly
    np.testing.assert_allclose(r.idio.values, (r.alpha + r.resid).values, atol=1e-12)

    # sum(epsilon) ~= 0 by OLS construction ...
    assert abs(r.resid.sum()) < 1e-8
    # ... but the cumulative idiosyncratic (alpha+eps) is NOT forced to zero — it holds the trend.
    assert abs(r.cum_idio.iloc[-1]) > 0.05           # ~ alpha * N ~= 0.36
    assert r.cum_idio.iloc[-1] == r.cum_idio.iloc[-1]  # not NaN


def test_additive_identity_cum_raw_equals_explained_plus_idio():
    stock, factors = _synthesize()
    r = run_regression(stock, factors)
    lhs = r.cum_raw_additive.values
    rhs = (r.cum_explained + r.cum_idio).values
    np.testing.assert_allclose(lhs, rhs, atol=1e-10)


def test_attribution_slices_sum_to_total():
    stock, factors = _synthesize()
    r = run_regression(stock, factors)
    attr = attribution(r)
    assert abs(attr["check"]) < 1e-9
    assert abs(sum(attr["slices"].values()) - attr["total"]) < 1e-9
