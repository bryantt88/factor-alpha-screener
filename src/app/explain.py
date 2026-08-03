"""On-demand "how to read this" explainer — the optional Gemini button (docs/PLATFORM.md).

The LLM EXPLAINS the already-computed numbers in plain language for a portfolio manager. It never
produces or estimates a figure (CLAUDE.md rule 1) — every number in the prompt is one the regression
computed. This is a read-only interpretation layer, distinct from Gate 3 (which sources exposure).
"""
from __future__ import annotations

from ..agent.gemini_client import call_gemini

_SYSTEM = (
    "You are a buy-side quant explaining ONE stock's FULL screening report to a portfolio manager. "
    "Write ONE clear, flowing paragraph (~180 words), plain-language and decision-oriented — no headers, "
    "no bullet lists, no markdown. Explain ONLY the numbers given; never invent, estimate, or add a "
    "figure. Walk the PM through the WHOLE report, in this order: (1) the verdict and how much confidence "
    "to place in it — is the move the stock's own story or a market/sector/factor ride, and is the "
    "own-story statistically real; (2) what actually DRIVES the stock, using the performance-driver "
    "shares and the idiosyncratic (own-story) share; (3) SIZE & RISK — call out the standout risk (high "
    "volatility, high market beta, or a deep drawdown); (4) the FINANCIAL health from the fundamentals "
    "gate; then (5) a one-sentence bottom line for a PM. "
    "CRITICAL LABELLING: 'market beta' means ONLY the simple 1-year market beta provided. Any per-factor "
    "beta is a PARTIAL beta (distorted by collinearity in multi-factor mode) — never call it market "
    "sensitivity. All returns given are COMPOUNDED; do not introduce any other return number."
)


def _facts(o, gate=None) -> str:
    r, tr = o.reg, o.trend
    mkt = r.simple_market_beta
    mkt_s = f"{mkt:+.2f}" if mkt is not None else "n/a (no market factor in this mode)"
    raw12 = f"{o.raw_12m:+.0%}" if o.raw_12m is not None else "n/a"
    idio_comp = f"{r.idio_return_compounded():+.0%}"

    # Performance drivers (variance shares) — only populated in drivers mode.
    v = getattr(o, "variance", None)
    if v is not None:
        drivers = ", ".join(f"{g} {s*100:.0f}%" for g, s in v.ordered())
        idio_share = f"{(1 - r.r2_adjusted) * 100:.0f}%"
    else:
        drivers = f"n/a (drivers mode only); model R² {r.r2:.2f}"
        idio_share = f"{(1 - r.r2) * 100:.0f}%"

    # Size & risk + financial health from the gate (best-effort; may be absent).
    mc_s, fin = "n/a", "unavailable"
    if gate:
        sz = gate.get("size")
        mc = getattr(sz, "market_cap", None) if sz is not None else None
        if mc:
            b = mc / 1e9
            mc_s = f"${b/1000:.2f}T" if b >= 1000 else f"${b:.1f}B"
        fund = gate.get("fund")
        if fund is not None and getattr(fund, "metrics", None):
            notes = "; ".join(f"{k.replace('_', ' ')}: {mv.note}" for k, mv in fund.metrics.items())
            fin = f"overall {fund.overall} — {notes}"
    vol = f"{r.annualized_volatility * 100:.0f}%"
    dd = f"{r.max_drawdown * 100:.0f}%"
    corr = ", ".join(f"{c} {d['corr']:+.2f}" for c, d in o.headline_corr.items()) or "n/a"

    return (
        f"Ticker: {o.ticker}   |   window: {r.n_obs} trading days\n"
        f"VERDICT: {tr.track_tag}\n"
        f"  {tr.verdict_line}\n"
        f"Confidence in the own-story: {tr.alpha_tier} (alpha t-stat {r.alpha_tstat:+.2f}; "
        f"|t|>=2 = statistically real)\n"
        f"PERFORMANCE DRIVERS — share of day-to-day variance: {drivers}\n"
        f"Idiosyncratic (own-story) share: {idio_share}\n"
        f"RETURN (compounded): raw price {raw12}; own-story idiosyncratic {idio_comp} "
        f"(= raw minus everything the factors explain)\n"
        f"SIZE & RISK: market cap {mc_s}; annualized volatility {vol}; "
        f"market beta (1y, simple) {mkt_s}; max drawdown {dd}\n"
        f"FINANCIAL HEALTH (fundamentals gate): {fin}\n"
        f"Commodity correlation (last year): {corr}\n"
    )


def explain_stock(o, gate=None, timeout: int = 180) -> str:
    """Return a plain-language 'how to read this WHOLE report' for one StockOutput, via the gemini CLI.
    `gate` (optional) = {'size':SizeVerdict, 'fund':FundVerdict} so the read can cover size + financials."""
    prompt = (
        "Here is one stock's full screening report. Explain how a portfolio manager should read the "
        "whole thing:\n\n" + _facts(o, gate)
    )
    return call_gemini(prompt, system=_SYSTEM, timeout=timeout)
