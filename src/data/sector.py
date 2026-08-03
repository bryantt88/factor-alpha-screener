"""Per-stock GICS sector → SPDR sector-ETF resolution (Performance-Drivers 'Sector' factor).

Each stock is regressed on ITS OWN sector, JPM-style: the Sector factor is stock-specific (Vertiv is
Industrials → XLI; Constellation is Utilities → XLU), unlike Style (measured across all 5 style ETFs).
We assign sector — it's a fact — but never fabricate it: if the sector can't be determined, we return
None and the stock simply carries no Sector factor (its variance falls to another group / idiosyncratic),
surfaced as a dropped factor rather than a guess (CLAUDE.md rule 2).

Resolution order: (1) an explicit override for the known power-stack universe (auditable, offline-safe);
(2) yfinance `.info` GICS sector mapped to the matching SPDR sector ETF; (3) None.
"""
from __future__ import annotations

# GICS sector -> SPDR select-sector ETF (the standard tradeable sector proxies).
GICS_SECTOR_ETF = {
    "Utilities": "XLU",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Technology": "XLK",
    "Information Technology": "XLK",
    "Materials": "XLB",
    "Basic Materials": "XLB",
    "Financials": "XLF",
    "Financial Services": "XLF",
    "Health Care": "XLV",
    "Healthcare": "XLV",
    "Consumer Staples": "XLP",
    "Consumer Defensive": "XLP",
    "Consumer Discretionary": "XLY",
    "Consumer Cyclical": "XLY",
    "Communication Services": "XLC",
    "Real Estate": "XLRE",
}

# Explicit, auditable overrides for the known universe (yfinance sector labels can be patchy/thematic).
UNIVERSE_SECTOR_ETF = {
    "CEG": "XLU", "VST": "XLU", "NRG": "XLU", "NEE": "XLU", "SO": "XLU", "DUK": "XLU",
    "TLN": "XLU", "PEG": "XLU", "AEP": "XLU", "D": "XLU",
    "VRT": "XLI", "ETN": "XLI", "GEV": "XLI", "PWR": "XLI", "EMR": "XLI", "ABBV": "XLV",
    "BE": "XLI",   # Bloom Energy — classed Industrials
}


def _yf_sector(ticker: str) -> str | None:
    """Best-effort GICS sector string from yfinance .info (None on any failure — never raises)."""
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info or {}
        return info.get("sector") or info.get("sectorKey") or None
    except Exception:
        return None


def sector_etf_for(ticker: str) -> str | None:
    """Resolve `ticker` to its GICS sector SPDR ETF, or None if undeterminable (never fabricated)."""
    t = ticker.upper()
    if t in UNIVERSE_SECTOR_ETF:
        return UNIVERSE_SECTOR_ETF[t]
    sec = _yf_sector(t)
    if sec:
        return GICS_SECTOR_ETF.get(sec.strip())
    return None


def sector_map_for(tickers) -> dict[str, str]:
    """{ticker: sector_etf} for the tickers whose sector resolves; unresolved names are omitted."""
    out: dict[str, str] = {}
    for t in tickers:
        etf = sector_etf_for(t)
        if etf:
            out[t.upper()] = etf
    return out
