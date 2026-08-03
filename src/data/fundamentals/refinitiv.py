"""`refinitiv` fundamentals backend: reads a one-time cached terminal pull (no live API, no cost).

The boss exports the watchlist's fundamental fields from a Refinitiv/LSEG terminal into a local file
(`data/refinitiv_fundamentals.csv`); this backend just reads it. Same {"values", "unverified"}
contract as PublicFundamentals, so flipping `fundamentals_source: refinitiv` is the only change.

CSV schema: one row per ticker, a `ticker` column plus any of the REQUIRED_FIELDS as columns. Missing
cells stay None/unverified — never guessed. See data/refinitiv_fundamentals.example.csv.
"""
from __future__ import annotations

import os

from .base import REQUIRED_FIELDS, FundamentalsBackend


class RefinitivFundamentals(FundamentalsBackend):
    def __init__(self, path: str = "data/refinitiv_fundamentals.csv"):
        self.path = path
        self._df = None
        self._loaded = False

    def _load(self):
        if self._loaded:
            return self._df
        self._loaded = True
        if os.path.isfile(self.path):
            import pandas as pd
            df = pd.read_csv(self.path)
            df.columns = [c.strip() for c in df.columns]
            if "ticker" in df.columns:
                df["ticker"] = df["ticker"].astype(str).str.upper().str.strip()
                self._df = df.set_index("ticker")
        return self._df

    def get_fundamentals(self, ticker: str) -> dict:
        import math
        df = self._load()
        vals = {k: None for k in REQUIRED_FIELDS}
        if df is not None and ticker.upper() in df.index:
            row = df.loc[ticker.upper()]
            for k in REQUIRED_FIELDS:
                if k in row.index:
                    v = row[k]
                    try:
                        v = float(v)
                        vals[k] = None if math.isnan(v) else v
                    except (TypeError, ValueError):
                        vals[k] = None
        unverified = {k for k in REQUIRED_FIELDS if vals[k] is None}
        return {"values": vals, "unverified": unverified}
