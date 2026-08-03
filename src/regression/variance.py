"""Performance-Drivers variance decomposition (Shapley / LMG) — the v2 panel's analytical core.

Splits a stock's RETURN VARIANCE into driver-group shares that sum to 100%:

    Σ_g  share_g   +   idiosyncratic   =   1
    (Market, Rates, Energy, …)             (= 1 − R² of the full model)

This is DIFFERENT math from the additive *return* attribution in attribution.py. There we split the
cumulative RETURN into factor slices; here we split the RETURN VARIANCE (risk) into driver groups —
the JPM "Performance Drivers" bar. The idiosyncratic share = 1 − R² is the α+ε own-merit thesis
restated as variance: the fraction of the stock's ups and downs the factors CAN'T explain.

Why Shapley / LMG and not one flat OLS split
--------------------------------------------
Driver groups are correlated (a sector ETF overlaps the market; oil overlaps gas; styles overlap the
market). If you just fit each group alone and read its R², the shares double-count the shared variance
and don't sum to the full-model R². LMG (Lindeman–Merenda–Gold, a.k.a. Shapley-regression) fixes this:
each group's share = the AVERAGE of its incremental R² (the R² it adds) over every possible ordering
of the groups. Properties we rely on:
  • order-independent (unlike a fixed hierarchical regression),
  • every share ≥ 0 (adding a regressor never lowers in-sample R², so each marginal contribution ≥ 0),
  • the group shares sum EXACTLY to R²(full); idiosyncratic takes the remaining 1 − R².
It is the transparent, returns-based cousin of a Barra covariance-based risk decomposition.

Cost is 2^k OLS fits where k = number of factor groups (4factor → 3 groups → 8 fits). Cheap.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from math import factorial

import numpy as np
import pandas as pd

IDIO_KEY = "Idiosyncratic"


@dataclass
class VarianceDecomposition:
    shares: dict[str, float]         # group name -> share of total variance (incl. IDIO_KEY); Σ ≈ 1.0
    r2: float                        # RAW R² of the full model (in-sample, before df-adjustment)
    groups: dict[str, list[str]]     # group name -> the factor columns that composed it
    r2_adjusted: float = 0.0         # df-adjusted R² (== explained_share == 1 − shares[IDIO_KEY])
    n_factors: int = 0               # total factor columns in the full model (the df correction's k)
    idio_key: str = IDIO_KEY

    @property
    def explained_share(self) -> float:
        """Total variance share explained by all factor groups together (== r2_adjusted)."""
        return float(sum(v for k, v in self.shares.items() if k != self.idio_key))

    def ordered(self) -> list[tuple[str, float]]:
        """Factor groups by descending share, then Idiosyncratic last — the JPM bar order."""
        fac = sorted(((g, s) for g, s in self.shares.items() if g != self.idio_key),
                     key=lambda kv: kv[1], reverse=True)
        return fac + [(self.idio_key, self.shares[self.idio_key])]


@dataclass
class DriverStability:
    """How much each driver group's variance share moves between the 1Y and 6M windows — a share is
    only trustworthy if it's roughly stable across the two. A big swing => the point estimate is noisy."""
    per_group: dict[str, dict]       # group -> {'long', 'short', 'delta'} (fractions of variance)
    unstable_groups: list[str]       # factor groups whose |1Y − 6M| share exceeds the threshold
    threshold: float
    max_delta: float                 # largest single-group |1Y − 6M| swing (factor groups only)


def stability(v_long: "VarianceDecomposition", v_short: "VarianceDecomposition",
              threshold: float = 0.10) -> DriverStability:
    """Compare two decompositions (1Y vs 6M) and flag factor groups that swing more than `threshold`
    (default 10 percentage points). The idiosyncratic group is tracked but never flagged — it moves as
    the complement of the others."""
    names = set(v_long.shares) | set(v_short.shares)
    per: dict[str, dict] = {}
    unstable: list[str] = []
    max_delta = 0.0
    for g in names:
        lo = float(v_long.shares.get(g, 0.0))
        sh = float(v_short.shares.get(g, 0.0))
        d = abs(lo - sh)
        per[g] = {"long": lo, "short": sh, "delta": d}
        if g != IDIO_KEY:
            max_delta = max(max_delta, d)
            if d > threshold:
                unstable.append(g)
    return DriverStability(per_group=per, unstable_groups=sorted(unstable),
                           threshold=threshold, max_delta=max_delta)


def _r2(y: np.ndarray, X: np.ndarray) -> float:
    """In-sample OLS R² of y on X (X already includes an intercept column). ss_tot from the mean of y.
    Returns 0.0 for a constant y (no variance to explain)."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    ss_res = float(resid @ resid)
    yc = y - y.mean()
    ss_tot = float(yc @ yc)
    if ss_tot <= 0.0:
        return 0.0
    return 1.0 - ss_res / ss_tot


def decompose_variance(stock_returns: pd.Series, factor_returns: pd.DataFrame,
                       groups: dict[str, list[str]]) -> VarianceDecomposition:
    """LMG / Shapley variance decomposition of `stock_returns` over driver `groups`.

    `groups` maps a group name to the factor columns (in `factor_returns`) it contains, e.g.
    {'Market': ['market'], 'Rates': ['rates'], 'Energy': ['oil', 'gas']} (see Config.driver_groups).
    Every group is added to / removed from the model as a BLOCK (all its columns together), so 5 style
    ETFs count as one 'Style' group, never five. Returns shares that sum to ~1.0 with idiosyncratic
    = 1 − R²(full).
    """
    y = stock_returns.to_numpy(dtype=float)
    n = len(y)
    ones = np.ones((n, 1))
    group_names = [g for g in groups if groups[g]]     # skip any empty group
    k = len(group_names)

    if k == 0:                                          # no factors → all variance is idiosyncratic
        return VarianceDecomposition(shares={IDIO_KEY: 1.0}, r2=0.0, groups=dict(groups),
                                     r2_adjusted=0.0, n_factors=0)

    cols = {g: factor_returns[groups[g]].to_numpy(dtype=float) for g in group_names}

    # R² for every subset of groups, cached by frozenset (each subset fit at most once).
    cache: dict[frozenset, float] = {frozenset(): 0.0}

    def r2_of(subset: tuple[str, ...]) -> float:
        key = frozenset(subset)
        if key not in cache:
            X = np.column_stack([ones] + [cols[g] for g in subset])
            cache[key] = _r2(y, X)
        return cache[key]

    # Shapley value of each group = weighted average of its marginal R² over all orderings.
    raw: dict[str, float] = {}
    for g in group_names:
        rest = [x for x in group_names if x != g]
        total = 0.0
        for size in range(len(rest) + 1):
            weight = factorial(size) * factorial(k - size - 1) / factorial(k)
            for subset in combinations(rest, size):
                total += weight * (r2_of(subset + (g,)) - r2_of(subset))
        raw[g] = max(0.0, float(total))                 # clamp tiny negative float noise (LMG ≥ 0)

    r2_full = r2_of(tuple(group_names))                 # raw in-sample R² (Σ raw == r2_full)

    # Degrees-of-freedom correction: in-sample R² is inflated when many (often correlated) factors are
    # fit on limited daily data, which would UNDERSTATE the idiosyncratic share. Use adjusted R² for the
    # explained/idiosyncratic split, and scale the LMG factor shares to sum to it — the RELATIVE
    # attribution among groups is unchanged; only the explained total is bias-corrected.
    n_factors = sum(cols[g].shape[1] for g in group_names)   # k = total regressors in the full model
    dof = n - n_factors - 1
    r2_adj = (1.0 - (1.0 - r2_full) * (n - 1) / dof) if dof > 0 else r2_full
    r2_adj = max(0.0, min(r2_adj, r2_full))
    scale = (r2_adj / r2_full) if r2_full > 0 else 0.0

    shares = {g: raw[g] * scale for g in group_names}   # shrink explained to the adjusted level
    shares[IDIO_KEY] = float(1.0 - r2_adj)
    return VarianceDecomposition(shares=shares, r2=float(r2_full), r2_adjusted=float(r2_adj),
                                 n_factors=int(n_factors),
                                 groups={g: list(groups[g]) for g in group_names})
