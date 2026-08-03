"""Additive return attribution (docs/REGRESSION.md §6) — feeds the waterfall (Output 3).

    total_return ~= sum(alpha) + sum_i(beta_i * sum(R_i)) + sum(epsilon)

The idiosyncratic slice = sum(alpha) + sum(epsilon) = the cum_idio endpoint = "the stock's own
contribution"; the factor slices are "explained by factors". Slices sum EXACTLY to the additive raw
endpoint (cum_raw_additive[-1]).
"""
from __future__ import annotations

from .engine import RegressionResult

IDIO_KEY = "idiosyncratic (α+ε)"  # "idiosyncratic (α+ε)"


def attribution(result: RegressionResult) -> dict:
    """Decompose the total (additive) return into per-factor slices + the idiosyncratic slice.

    Returns {'slices': {name: value}, 'idio_key': str, 'total': float, 'check': float}
    where `check` is (sum of slices - total) and should be ~0 (the additive identity).
    """
    fr = result.factor_returns
    slices: dict[str, float] = {}
    for f, beta in result.betas.items():
        slices[f] = float(beta * fr[f].sum())
    slices[IDIO_KEY] = float(result.cum_idio.iloc[-1])       # sum(alpha) + sum(epsilon)

    total = float(result.cum_raw_additive.iloc[-1])
    return {
        "slices": slices,
        "idio_key": IDIO_KEY,
        "total": total,
        "check": float(sum(slices.values()) - total),
    }
