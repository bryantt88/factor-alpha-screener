"""`public` fundamentals backend (default, v1): best-effort free data via yfinance.

Returns {"values": {field: value|None}, "unverified": {field, ...}}. Any field that can't be pulled
reliably is None and listed in `unverified` — surfaced visibly in the scorecard, never guessed
(CLAUDE.md rule 2). Public financials are patchy, so several fields are routinely unverified; the
`refinitiv` backend (Step 3) fills them from a clean one-time terminal pull.
"""
from __future__ import annotations

import math

from .base import REQUIRED_FIELDS, FundamentalsBackend


def _num(x):
    try:
        if x is None:
            return None
        x = float(x)
        return None if math.isnan(x) else x
    except Exception:
        return None


class PublicFundamentals(FundamentalsBackend):
    def get_fundamentals(self, ticker: str) -> dict:
        import yfinance as yf

        t = yf.Ticker(ticker)
        try:
            info = t.info or {}
        except Exception:
            info = {}

        vals = {k: None for k in REQUIRED_FIELDS}
        ebitda = _num(info.get("ebitda"))
        revenue = _num(info.get("totalRevenue"))
        vals["ebitda"] = ebitda
        if ebitda is not None and revenue:
            vals["ebitda_margin"] = ebitda / revenue
        vals["ebitda_margin_yoy"] = self._margin_yoy(t)

        total_debt = _num(info.get("totalDebt"))
        cash = _num(info.get("totalCash"))
        if total_debt is not None and cash is not None:
            vals["net_debt"] = total_debt - cash
        if vals["net_debt"] is not None and ebitda:
            vals["net_debt_to_ebitda"] = vals["net_debt"] / ebitda

        eps_a, eps_c = self._last_eps(t)
        vals["last_eps_actual"] = eps_a
        vals["last_eps_consensus"] = eps_c
        # revenue actual/consensus not reliably public -> left None (unverified)

        # NOTE: yfinance exposes trailing EV/EBITDA ('enterpriseToEbitda'); a true FORWARD figure and
        # a 3-yr median are not reliably available publicly -> both unverified here (Refinitiv fills).
        vals["fwd_ev_ebitda"] = _num(info.get("enterpriseToEbitda"))

        unverified = {k for k in REQUIRED_FIELDS if vals[k] is None}
        return {"values": vals, "unverified": unverified}

    def _margin_yoy(self, t):
        """Latest-vs-prior annual EBITDA-margin change, or None if not cleanly computable."""
        try:
            fin = t.income_stmt
            rev = fin.loc["Total Revenue"]
            eb = None
            for key in ("EBITDA", "Normalized EBITDA"):
                if key in fin.index:
                    eb = fin.loc[key]
                    break
            if eb is None:
                return None
            cols = list(fin.columns)[:2]
            if len(cols) < 2:
                return None
            m0 = _num(eb[cols[0]]) / _num(rev[cols[0]])
            m1 = _num(eb[cols[1]]) / _num(rev[cols[1]])
            return float(m0 - m1)
        except Exception:
            return None

    def _last_eps(self, t):
        """(reported EPS, consensus EPS) for the most recent reported quarter, or (None, None)."""
        try:
            df = t.get_earnings_dates(limit=8)
            past = df[df["Reported EPS"].notna()]
            if len(past):
                row = past.iloc[0]
                a = _num(row.get("Reported EPS"))
                c = _num(row.get("EPS Estimate"))
                return a, c
        except Exception:
            pass
        return None, None
