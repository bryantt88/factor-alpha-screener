"""Commodity relationship diagnostics (docs/OUTPUTS.md §2, refined for this project).

TWO distinct things — do not conflate them:
  (a) HEADLINE static correlation + beta over the full window (corr_headline_days, 252d). One number
      per commodity answering "how correlated is this stock with oil/gas over the LAST YEAR?"
  (b) ROLLING correlation (rolling_corr_days, ~63d) + rolling beta (rolling_beta_days, 90d). The
      window MUST be << the sample, or you get one useless point. The DECOUPLING trajectory.

Neither builds the primary idiosyncratic line — that is the static 252d multivariate fit in engine.py
(REGRESSION §5: never fit beta on a short window and apply it to a long one).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def static_correlation(stock_returns: pd.Series, commodity_returns: pd.DataFrame) -> dict[str, dict]:
    """Full-window Pearson correlation + univariate beta of the stock vs each commodity.

    Returns {commodity: {'corr': float, 'beta': float}}. beta = Cov(stock, comm) / Var(comm).
    The caller passes the slice defining the window (e.g. the last corr_headline_days rows).
    """
    out: dict[str, dict] = {}
    for c in commodity_returns.columns:
        comm = commodity_returns[c]
        var = float(comm.var())
        out[c] = {
            "corr": float(stock_returns.corr(comm)),
            "beta": float(stock_returns.cov(comm) / var) if var else float("nan"),
        }
    return out


def factor_correlation_table(frame: pd.DataFrame, ticker: str, factor_cols: list[str],
                             short: int, long: int) -> dict[str, dict]:
    """JPM-style per-factor correlation table: univariate Pearson corr of the stock vs each factor over
    the last `short` (6M) and `long` (1Y) trading days. Returns {factor: {'corr6m', 'corr1y'}}.

    Univariate (single-factor) correlation, distinct from the multivariate partial betas in the model —
    it answers "how does this stock co-move with each driver," the JPM factor table's question."""
    s_short, s_long = frame[ticker].tail(short), frame[ticker].tail(long)
    out: dict[str, dict] = {}
    for f in factor_cols:
        out[f] = {
            "corr6m": float(s_short.corr(frame[f].tail(short))),
            "corr1y": float(s_long.corr(frame[f].tail(long))),
        }
    return out


def rolling_correlation(stock_returns: pd.Series, commodity_returns: pd.DataFrame, window: int) -> pd.DataFrame:
    """Rolling Pearson correlation of the stock vs each commodity. Window must be << the sample."""
    return pd.DataFrame(
        {c: stock_returns.rolling(window).corr(commodity_returns[c]) for c in commodity_returns.columns}
    )


def rolling_beta(stock_returns: pd.Series, commodity_returns: pd.DataFrame, window: int) -> pd.DataFrame:
    """Rolling univariate beta of the stock vs each commodity: Cov_w(stock, comm) / Var_w(comm)."""
    out = {}
    for c in commodity_returns.columns:
        comm = commodity_returns[c]
        cov = stock_returns.rolling(window).cov(comm)
        var = comm.rolling(window).var()
        out[c] = cov / var
    return pd.DataFrame(out)


def rolling_partial_beta(stock_returns: pd.Series, factor_returns: pd.DataFrame,
                         window: int) -> pd.DataFrame:
    """Rolling MULTIVARIATE (partial) betas — the same kind the main model reports, over a moving
    `window`. Fits OLS (with intercept) of the stock on ALL factors in each trailing window, so the
    decoupling chart uses the identical beta definition as the scorecard/table (no univariate mismatch).
    Returns a DataFrame indexed like the input, one column per factor (NaN until the first full window).
    """
    y = stock_returns.to_numpy(dtype=float)
    factors = factor_returns.to_numpy(dtype=float)
    n = len(y)
    cols = list(factor_returns.columns)
    Xc = np.column_stack([np.ones(n), factors])          # intercept + factors
    out = np.full((n, len(cols)), np.nan)
    for end in range(window, n + 1):
        Xw, yw = Xc[end - window:end], y[end - window:end]
        try:
            beta, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
            out[end - 1, :] = beta[1:]                    # drop the intercept
        except Exception:
            pass
    return pd.DataFrame(out, index=factor_returns.index, columns=cols)
