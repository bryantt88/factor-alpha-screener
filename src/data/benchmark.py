"""Relative strength vs a type-appropriate sector benchmark (Output 4, docs/OUTPUTS.md).

The benchmark is auto-picked from the Gate-3 type via config.benchmark_map (e.g. nuclear→XLU,
equipment→XLI, renewable→ICLN). Relative strength = the stock's cumulative return minus the
benchmark's, over the same window — the AI premium above the sector tide.
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd

from .prices import daily_returns, fetch_prices


def benchmark_for_type(type_: str, benchmark_map: dict) -> str | None:
    return benchmark_map.get(type_)


def relative_strength(stock_returns: pd.Series, benchmark_ticker: str) -> pd.Series | None:
    """Cumulative excess return (stock − benchmark), additive, in percentage points, aligned to the
    stock's window. None if the benchmark can't be pulled."""
    idx = stock_returns.index
    start = idx.min() - _dt.timedelta(days=10)
    end = idx.max() + _dt.timedelta(days=2)
    px = fetch_prices([benchmark_ticker], start, end)
    if px is None or benchmark_ticker not in px.columns:
        return None
    br = daily_returns(px)[benchmark_ticker]
    j = pd.concat([stock_returns.rename("s"), br.rename("b")], axis=1, join="inner").dropna()
    if j.empty:
        return None
    return ((j["s"].cumsum() - j["b"].cumsum()) * 100.0).rename("rel")
