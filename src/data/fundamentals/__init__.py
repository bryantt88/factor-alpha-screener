"""Swappable fundamentals backend: `public` (default, v1) or `refinitiv` (cached one-time pull).

Identical function signatures behind one interface (base.py) — flipping source is a config change.
Missing/unreliable fields return None + `unverified`, never a guess (CLAUDE.md rule 2).
"""
from __future__ import annotations


def get_backend(source: str = "edgar", refinitiv_path: str = "data/refinitiv_fundamentals.csv"):
    """Return the fundamentals backend for `source`:
      'edgar'     — SEC filed financials (primary source, free, credible) — DEFAULT
      'refinitiv' — a cached terminal-export CSV
      'public'    — best-effort yfinance (patchy; kept as a fast fallback)
    """
    if source == "refinitiv":
        from .refinitiv import RefinitivFundamentals
        return RefinitivFundamentals(refinitiv_path)
    if source == "public":
        from .public import PublicFundamentals
        return PublicFundamentals()
    from .edgar import EdgarFundamentals
    return EdgarFundamentals()
