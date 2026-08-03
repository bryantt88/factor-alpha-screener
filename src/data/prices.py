"""Price & return pulls via yfinance (public, free) — powers the whole regression + all charts.

Daily adjusted-close prices and daily returns for stocks and factor proxies. Each stock is aligned to
the factor panel independently (inner join on common trading days), so a short-history name never
truncates the others. Tickers with insufficient history are reported, never silently faked.
"""
from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ReturnPanel:
    """Aligned daily returns ready for regression + rolling diagnostics.

    factor_returns : DataFrame indexed by date, columns = LOGICAL factor names (market/rates/oil/gas).
    stocks         : ticker -> DataFrame [ticker, *logical factors] over the full pulled window,
                     inner-joined with the factors (so rolling has warm-up history before the horizon).
    skipped        : list of (ticker, reason) for names dropped for insufficient/aligned data.
    """
    factor_returns: pd.DataFrame
    stocks: dict[str, pd.DataFrame] = field(default_factory=dict)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    dropped_factors: list[str] = field(default_factory=list)   # shared factors that failed to download


def fetch_prices(tickers, start, end) -> pd.DataFrame:
    """Daily auto-adjusted close for `tickers` over [start, end) as a DataFrame (ticker columns)."""
    import yfinance as yf

    tickers = list(dict.fromkeys(tickers))  # dedupe, preserve order
    data = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False, threads=True)
    if data is None or len(data) == 0:
        return pd.DataFrame()
    # Multi-ticker -> MultiIndex columns (field, ticker); single-ticker may be flat columns.
    if isinstance(data.columns, pd.MultiIndex):
        close = data["Close"].copy()
    else:
        close = data[["Close"]].copy()
        close.columns = [tickers[0]]
    return close.dropna(how="all")


def daily_returns(prices: pd.DataFrame) -> pd.DataFrame:
    """Daily simple returns from a price DataFrame (drop the leading NaN row)."""
    return prices.pct_change().dropna(how="all")


def _pull_window_days(horizon: int, warmup: int, buffer_days: int = 20) -> int:
    """Calendar days to request so we get `horizon + warmup` trading-day returns with room to spare
    (~252 trading days per 365 calendar days => ~0.69 ratio)."""
    trading_needed = horizon + warmup + 1
    return math.ceil(trading_needed / 0.69) + buffer_days


def build_return_panel(
    stock_tickers,
    factor_map: dict[str, str],
    horizon: int,
    as_of_date: _dt.date,
    warmup: int = 90,
    sector_by_ticker: dict[str, str] | None = None,
) -> ReturnPanel:
    """Build a ReturnPanel: factor returns (logical-named) + per-stock aligned return frames.

    `factor_map` is {logical_name: proxy_ticker}, e.g. {'market':'SPY','oil':'CL=F',...}.
    `sector_by_ticker` (Performance-Drivers mode) maps {ticker: sector_ETF}; when present, each stock's
    frame gains a 'sector' column = that stock's OWN sector-ETF return (per-stock factor, JPM-style).

    Each stock frame spans the full pulled window (horizon + warmup) so rolling diagnostics cover the
    displayed horizon without warm-up gaps; callers take `.tail(horizon)` for the regression itself.
    Robust: a shared factor whose proxy fails to download is dropped (recorded in `dropped_factors`),
    never crashing the run and never fabricated.
    """
    start = as_of_date - _dt.timedelta(days=_pull_window_days(horizon, warmup))
    end = as_of_date + _dt.timedelta(days=1)  # yfinance end is exclusive; include as_of_date

    proxy_by_logical = dict(factor_map)
    factor_px = fetch_prices(list(proxy_by_logical.values()), start, end)
    factor_ret = daily_returns(factor_px)
    # rename proxy tickers -> logical names; keep only logicals that actually returned data (robust)
    inv = {proxy: logical for logical, proxy in proxy_by_logical.items()}
    factor_ret = factor_ret.rename(columns=inv)
    available = [lg for lg in proxy_by_logical if lg in factor_ret.columns]
    dropped = [lg for lg in proxy_by_logical if lg not in factor_ret.columns]
    factor_ret = factor_ret[available].dropna(how="any")

    # Per-stock sector ETFs (distinct set), fetched once and sliced per stock.
    sector_by_ticker = {k.upper(): v for k, v in (sector_by_ticker or {}).items()}
    sector_ret = pd.DataFrame()
    sector_etfs = sorted(set(sector_by_ticker.values()))
    if sector_etfs:
        sector_ret = daily_returns(fetch_prices(sector_etfs, start, end))

    stock_px = fetch_prices(list(stock_tickers), start, end)
    stock_ret = daily_returns(stock_px)

    panel = ReturnPanel(factor_returns=factor_ret, dropped_factors=dropped)
    min_rows = max(30, horizon // 2)  # need a usable sample; half the horizon is the floor
    for t in stock_tickers:
        if t not in stock_ret.columns:
            panel.skipped.append((t, "no price data returned by yfinance"))
            continue
        s = stock_ret[t].dropna()
        parts = [s.rename(t), factor_ret]
        etf = sector_by_ticker.get(t.upper())
        if etf and etf in sector_ret.columns:
            parts.append(sector_ret[etf].rename("sector"))   # this stock's own sector factor
        frame = pd.concat(parts, axis=1, join="inner").dropna(how="any")
        if len(frame) < min_rows:
            panel.skipped.append((t, f"only {len(frame)} aligned trading days (< {min_rows} needed)"))
            continue
        panel.stocks[t] = frame
    return panel
