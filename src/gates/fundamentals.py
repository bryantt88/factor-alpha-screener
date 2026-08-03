"""Gate 2 — Fundamentals (deterministic, SPEC §3 / DATA.md). Lean, decision-relevant metric set:

  - EBITDA margin + YoY trend   (positive + non-deteriorating)
  - net debt / EBITDA           (below the config leverage flag)
  - last earnings surprise %    (positive = beat)
  - EV/EBITDA vs own 3yr median (FLAG if rich, do NOT fail)

Every metric is pass / flag / fail / unverified. `unverified` (a null we couldn't pull) never counts
as a fail — it's surfaced honestly. Overall fails only on a hard-metric fail; valuation is flag-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field

HARD_METRICS = ("ebitda_margin", "net_debt_to_ebitda", "earnings_surprise")


@dataclass
class MetricVerdict:
    status: str            # "pass" | "flag" | "fail" | "unverified"
    value: float | None
    note: str


@dataclass
class FundVerdict:
    overall: str           # "pass" | "flag" | "fail" | "unverified"
    metrics: dict = field(default_factory=dict)


def check_fundamentals(fund: dict, leverage_flag: float) -> FundVerdict:
    vals = fund["values"]
    basis = fund.get("basis")          # flow-item basis ('TTM->..' | 'FYxxxx') — appended to flow notes
    sfx = f" [{basis}]" if basis else ""
    m: dict[str, MetricVerdict] = {}

    # EBITDA margin + trend
    margin, yoy = vals["ebitda_margin"], vals["ebitda_margin_yoy"]
    if margin is None:
        m["ebitda_margin"] = MetricVerdict("unverified", None, "EBITDA margin unavailable")
    elif margin <= 0:
        m["ebitda_margin"] = MetricVerdict("fail", margin, f"{margin:.1%} (non-positive)")
    elif yoy is None:
        m["ebitda_margin"] = MetricVerdict("flag", margin, f"{margin:.1%}, YoY trend unverified")
    elif yoy < 0:
        m["ebitda_margin"] = MetricVerdict("flag", margin, f"{margin:.1%}, YoY {yoy:+.1%} (deteriorating)")
    else:
        m["ebitda_margin"] = MetricVerdict("pass", margin, f"{margin:.1%}, YoY {yoy:+.1%}")

    # net debt / EBITDA
    nde = vals["net_debt_to_ebitda"]
    if nde is None:
        m["net_debt_to_ebitda"] = MetricVerdict("unverified", None, "net debt/EBITDA unavailable")
    else:
        status = "pass" if nde <= leverage_flag else "fail"
        m["net_debt_to_ebitda"] = MetricVerdict(status, nde, f"{nde:.1f}x vs {leverage_flag:.0f}x flag")

    # earnings surprise
    a, c = vals["last_eps_actual"], vals["last_eps_consensus"]
    if a is None or c is None or c == 0:
        m["earnings_surprise"] = MetricVerdict("unverified", None, "EPS surprise unavailable")
    else:
        surp = (a - c) / abs(c)
        status = "pass" if surp > 0 else "fail"
        m["earnings_surprise"] = MetricVerdict(status, surp, f"{surp:+.1%} vs consensus (beat)" if surp > 0
                                               else f"{surp:+.1%} vs consensus (miss)")

    # valuation — FLAG only, never a fail
    ev, med = vals["fwd_ev_ebitda"], vals["ev_ebitda_3yr_median"]
    if ev is None:
        m["valuation"] = MetricVerdict("unverified", None, "EV/EBITDA unavailable")
    elif med is None:
        m["valuation"] = MetricVerdict("flag", ev, f"EV/EBITDA {ev:.1f}x (own 3yr median unverified)")
    elif ev > med:
        m["valuation"] = MetricVerdict("flag", ev, f"{ev:.1f}x vs {med:.1f}x median (rich)")
    else:
        m["valuation"] = MetricVerdict("pass", ev, f"{ev:.1f}x vs {med:.1f}x median")

    # label the flow-derived metrics with their basis (TTM vs fiscal year) — auditable in every cell
    if basis:
        for k in ("ebitda_margin", "net_debt_to_ebitda", "valuation"):
            if k in m and m[k].status != "unverified":
                m[k].note += sfx

    hard = [m[k].status for k in HARD_METRICS]
    if "fail" in hard:
        overall = "fail"
    elif all(s == "pass" for s in hard):
        overall = "pass"
    elif all(s == "unverified" for s in hard):
        overall = "unverified"
    else:
        overall = "flag"
    return FundVerdict(overall, m)
