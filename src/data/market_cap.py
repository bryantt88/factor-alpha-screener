"""Market capitalization for Gate 1 via yfinance. Returns None (never a guess) if unavailable."""
from __future__ import annotations


def get_market_cap(ticker: str) -> float | None:
    """Current market cap in USD, or None if it can't be pulled (flagged, never fabricated)."""
    import yfinance as yf

    t = yf.Ticker(ticker)
    # fast_info is the quick, reliable path
    try:
        mc = t.fast_info["market_cap"]
        if mc:
            return float(mc)
    except Exception:
        pass
    try:
        mc = (t.info or {}).get("marketCap")
        if mc:
            return float(mc)
    except Exception:
        pass
    return None
