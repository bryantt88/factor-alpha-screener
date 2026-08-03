"""Offline correctness proof for the Performance-Drivers variance decomposition + robust SEs.

The auditable heart-check: synthesize returns with KNOWN factor structure, then assert the LMG/Shapley
decomposition has the properties we promised the user —
  - shares are non-negative and sum to 1.0
  - idiosyncratic share == 1 - R²(full model), matching the engine's R²
  - order-independent (shuffling the factor columns doesn't move the shares)
  - orthogonal factors get shares proportional to their own explained variance (β²·Var)
  - oil + gas collapse into a single ENERGY group
And that HAC (Newey-West) robust SEs leave the point estimates (α, β, R²) identical to classical OLS.
"""
import numpy as np
import pandas as pd
import statsmodels.api as sm

from src.regression.engine import run_regression
from src.regression.variance import (IDIO_KEY, VarianceDecomposition,
                                     decompose_variance, stability)

N = 600


def _synthesize(betas, alpha=0.0004, noise_sd=0.006, seed=7):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=N, freq="B")
    factors = pd.DataFrame({name: rng.normal(0.0, 0.011, N) for name in betas}, index=idx)
    eps = rng.normal(0.0, noise_sd, N)
    stock = alpha + sum(betas[f] * factors[f] for f in betas) + eps
    return pd.Series(stock, index=idx, name="TEST"), factors


def test_shares_nonnegative_and_sum_to_one():
    stock, factors = _synthesize({"market": 1.1, "rates": -0.3, "oil": 0.2, "gas": 0.5})
    groups = {"Market": ["market"], "Rates": ["rates"], "Energy": ["oil", "gas"]}
    v = decompose_variance(stock, factors, groups)

    assert all(s >= 0.0 for s in v.shares.values()), v.shares
    assert abs(sum(v.shares.values()) - 1.0) < 1e-9, v.shares


def test_idiosyncratic_share_equals_one_minus_adjusted_r2():
    stock, factors = _synthesize({"market": 1.1, "rates": -0.3, "oil": 0.2, "gas": 0.5})
    groups = {"Market": ["market"], "Rates": ["rates"], "Energy": ["oil", "gas"]}
    v = decompose_variance(stock, factors, groups)
    reg = run_regression(stock, factors)

    # raw R² matches the engine; idiosyncratic = 1 - ADJUSTED R² (df-corrected); shares sum to adj R².
    assert abs(v.r2 - reg.r2) < 1e-9
    assert abs(v.r2_adjusted - reg.r2_adjusted) < 1e-9
    assert abs(v.shares[IDIO_KEY] - (1.0 - reg.r2_adjusted)) < 1e-9
    assert abs(v.explained_share - reg.r2_adjusted) < 1e-9


def test_adjusted_r2_raises_idiosyncratic_vs_raw():
    # With many correlated factors the df-adjustment must LOWER explained / RAISE idiosyncratic.
    stock, factors = _synthesize({"market": 1.1, "rates": -0.3, "oil": 0.2, "gas": 0.5})
    groups = {"Market": ["market"], "Rates": ["rates"], "Energy": ["oil", "gas"]}
    v = decompose_variance(stock, factors, groups)
    assert v.r2_adjusted <= v.r2
    assert v.shares[IDIO_KEY] >= (1.0 - v.r2) - 1e-12    # idio no smaller than the raw-R² implied one
    assert v.n_factors == 4


def test_order_independent():
    stock, factors = _synthesize({"market": 1.1, "rates": -0.3, "oil": 0.2, "gas": 0.5})
    g1 = {"Market": ["market"], "Rates": ["rates"], "Energy": ["oil", "gas"]}
    v1 = decompose_variance(stock, factors, g1)

    # shuffle both the group order AND the factor-column order
    factors2 = factors[["gas", "market", "oil", "rates"]]
    g2 = {"Energy": ["gas", "oil"], "Rates": ["rates"], "Market": ["market"]}
    v2 = decompose_variance(stock, factors2, g2)

    for grp in ("Market", "Rates", "Energy", IDIO_KEY):
        assert abs(v1.shares[grp] - v2.shares[grp]) < 1e-9, (grp, v1.shares, v2.shares)


def test_orthogonal_factors_split_by_explained_variance():
    # Two (approximately) independent factors, tiny noise: each group's share should be proportional
    # to its own β²·Var(factor) — the analytic explained-variance split.
    stock, factors = _synthesize({"a": 1.0, "b": 0.5}, alpha=0.0, noise_sd=1e-4, seed=3)
    groups = {"A": ["a"], "B": ["b"]}
    v = decompose_variance(stock, factors, groups)

    var_a = (1.0 ** 2) * factors["a"].var()
    var_b = (0.5 ** 2) * factors["b"].var()
    expected_ratio = var_a / var_b
    got_ratio = v.shares["A"] / v.shares["B"]
    assert abs(got_ratio - expected_ratio) / expected_ratio < 0.05, (got_ratio, expected_ratio)
    assert v.shares[IDIO_KEY] < 0.01                      # almost all variance is explained


def test_oil_and_gas_collapse_into_one_energy_group():
    stock, factors = _synthesize({"market": 1.0, "oil": 0.4, "gas": 0.4})
    groups = {"Market": ["market"], "Energy": ["oil", "gas"]}
    v = decompose_variance(stock, factors, groups)

    assert "Energy" in v.shares and "oil" not in v.shares and "gas" not in v.shares
    assert v.groups["Energy"] == ["oil", "gas"]
    assert set(v.shares) == {"Market", "Energy", IDIO_KEY}


def test_single_group_share_equals_adjusted_r2():
    stock, factors = _synthesize({"market": 1.2})
    v = decompose_variance(stock, factors, {"Market": ["market"]})
    reg = run_regression(stock, factors)
    assert abs(v.shares["Market"] - reg.r2_adjusted) < 1e-9   # one group -> its share IS the adj R²


def test_stability_flags_large_swings_only():
    long = VarianceDecomposition(
        shares={"Market": 0.50, "Energy": 0.20, IDIO_KEY: 0.30}, r2=0.70,
        groups={"Market": ["market"], "Energy": ["oil"]}, r2_adjusted=0.70)
    short = VarianceDecomposition(
        shares={"Market": 0.25, "Energy": 0.22, IDIO_KEY: 0.53}, r2=0.47,
        groups={"Market": ["market"], "Energy": ["oil"]}, r2_adjusted=0.47)
    st = stability(long, short, threshold=0.10)

    assert "Market" in st.unstable_groups          # 0.50 -> 0.25 = 25pp swing
    assert "Energy" not in st.unstable_groups       # 0.20 -> 0.22 = 2pp, stable
    assert IDIO_KEY not in st.unstable_groups        # idiosyncratic never flagged (it's the complement)
    assert abs(st.max_delta - 0.25) < 1e-9


def test_hac_leaves_point_estimates_identical_to_classical_ols():
    stock, factors = _synthesize({"market": 1.1, "rates": -0.3, "oil": 0.2, "gas": 0.5})
    reg = run_regression(stock, factors)                 # HAC (Newey-West) SEs

    X = sm.add_constant(factors, has_constant="add")
    classical = sm.OLS(stock.astype(float), X).fit()     # classical SEs

    # α, betas, R² are IDENTICAL — only the SEs/pvalues differ.
    assert abs(reg.alpha - float(classical.params["const"])) < 1e-12
    for f in factors.columns:
        assert abs(reg.betas[f] - float(classical.params[f])) < 1e-12
    assert abs(reg.r2 - float(classical.rsquared)) < 1e-12
    assert reg.cov_type == "HAC" and reg.hac_maxlags and reg.hac_maxlags >= 1
