"""Serialise a ScreenResult to a JSON-safe dict — the contract the React front-end consumes.

Every number here is COMPUTED by the pipeline (never fabricated); nulls surface as JSON null. The
chart series are pre-cumulated so the front-end just plots arrays. Compounded convention throughout
(matching the app), except the attribution slices, which are the one additive breakdown.
"""
from __future__ import annotations

import math

from ..gates.trend import DRIVERS_MODE_CAVEAT, combined_oil_beta
from ..opportunity import build_opportunities
from ..viz.charts import build_scorecard


def _num(x):
    """JSON-safe float: NaN/inf -> None, numpy -> float."""
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _series(s):
    return {"dates": [d.strftime("%Y-%m-%d") for d in s.index], "values": [_num(v) for v in s]}


def _stock_payload(o, factor_map=None, custom_groups=None) -> dict:
    r, tr = o.reg, o.trend
    return {
        "ticker": o.ticker,
        "track": tr.track_tag,
        "trackShort": tr.track_tag.split(" — ")[0],
        "verdictLine": tr.verdict_line,
        "alphaVerdict": tr.alpha_verdict,
        "alphaTier": tr.alpha_tier,       # "Real" | "Not proven" | "Likely luck" (plain confidence tag)
        "trackingNoise": bool(tr.tracking_noise),
        "trackingNoiseNote": tr.tracking_noise_note,
        "metrics": {
            "alphaAnnualized": _num(tr.alpha_annualized),
            "alphaTstat": _num(tr.alpha_tstat),
            "alphaPvalue": _num(tr.alpha_pvalue),
            "informationRatio": _num(tr.information_ratio),
            "alphaSignificant": bool(tr.alpha_significant),
            "idioEndpoint": _num(tr.idio_endpoint),
            "raw12m": _num(o.raw_12m),
            "raw6m": _num(o.raw_6m),
            "r2": _num(r.r2),
            "combinedOilBeta": _num(combined_oil_beta(r)),
            # Size & Risk card (all COMPUTED from prices — never fabricated). marketBeta is the SIMPLE
            # univariate market beta (the recognisable "beta"), NOT the partial beta used in the driver
            # split; None outside market-bearing modes.
            "marketBeta": _num(r.simple_market_beta),
            "annualizedVol": _num(r.annualized_volatility),
            "maxDrawdown": _num(r.max_drawdown),
        },
        "betas": {k: _num(v) for k, v in r.betas.items()},
        "pvalues": {k: _num(v) for k, v in r.pvalues.items()},
        "series": {
            "raw": _series(r.cum_raw_compounded * 100.0),
            "idio": _series(r.cum_idio_compounded * 100.0),
            "alphaDrift": _series(r.cum_alpha_drift * 100.0),
        },
        "attribution": _attribution_payload(o.attr),
        "drivers": _variance_payload(getattr(o, "variance", None),
                                     getattr(o, "driver_stability", None)),
        "factorTable": _factor_table_payload(getattr(o, "factor_table", None),
                                             getattr(o, "sector_etf", None),
                                             factor_map, custom_groups),
        "regressionFit": {
            "predicted": [_num(v) for v in (r.predicted * 100.0)],
            "actual": [_num(v) for v in (r.stock_returns * 100.0)],
        },
        "headlineCorr": {c: {"corr": _num(d.get("corr")), "beta": _num(d.get("beta"))}
                         for c, d in (getattr(o, "headline_corr", {}) or {}).items()},
        "rolling": _rolling_payload(o),
    }


def _rolling_payload(o) -> dict:
    """Rolling correlation (univariate) + rolling partial beta (multivariate — matches the model).
    Static references: correlation = the 1-yr univariate corr; beta = the model's partial beta (the
    same number in the scorecard/table), so the dashed line is exactly the table value."""
    rc, rb = getattr(o, "roll_corr", None), getattr(o, "roll_beta", None)
    hc = getattr(o, "headline_corr", {}) or {}
    betas = o.reg.betas
    if rc is None or rb is None or len(rc.columns) == 0:
        return {"dates": [], "corr": {}, "beta": {}, "staticCorr": {}, "staticBeta": {}}
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in rc.index],
        "corr": {c: [_num(v) for v in rc[c]] for c in rc.columns},
        "beta": {c: [_num(v) for v in rb[c]] for c in rb.columns},
        "staticCorr": {c: _num(hc[c]["corr"]) for c in hc},
        "staticBeta": {c: _num(betas.get(c)) for c in rb.columns},
    }


# Readable display names per logical factor; the ACTUAL proxy ticker is appended from the run's
# factor_map so the label always matches the data used (US 'Market (SPY)' vs Indonesia 'Market (^JKSE)').
_FACTOR_DISPLAY = {
    "market": "Market", "rates": "Rates", "oil": "Oil", "gas": "Gas", "brent": "Brent",
    "value": "Value", "growth": "Growth", "momentum": "Momentum", "lowvol": "Low Vol",
    "quality": "Quality", "credit": "Credit", "metals": "Base Metals", "fx": "FX", "em": "EM",
}


def _factor_label(f: str, proxy) -> str:
    name = _FACTOR_DISPLAY.get(f, f.replace("_", " ").capitalize())
    return f"{name} ({proxy})" if proxy else name


def _factor_table_payload(table, sector_etf, factor_map=None, custom_groups=None) -> list | None:
    """JPM-style factor table rows: per-factor 6M/1Y univariate correlation, tagged with its driver
    group so the front-end can render grouped rows. The label shows the REAL proxy ticker for THIS run
    (not a hardcoded US default). None when no table (non-drivers runs may be empty)."""
    if not table:
        return None
    from ..config import FACTOR_GROUPS
    factor_map = factor_map or {}
    custom_groups = custom_groups or {}
    rows = []
    for f, d in table.items():
        if f == "sector":
            label, group = f"Sector ({sector_etf})", "Sector"
        else:
            label = _factor_label(f, factor_map.get(f))
            group = custom_groups.get(f) or FACTOR_GROUPS.get(f, f.capitalize())
        rows.append({
            "factor": f,
            "label": label,
            "group": group,
            "corr6m": _num(d.get("corr6m")),
            "corr1y": _num(d.get("corr1y")),
        })
    return rows


def _variance_payload(v, stab=None) -> dict | None:
    """Performance-Drivers variance shares: one entry per driver group (desc) + Idiosyncratic last,
    the raw + adjusted R², each group's factor members, and (if available) the 1Y-vs-6M stability
    report. Shares are percentages summing to ~100 (built off the df-adjusted R²)."""
    if v is None:
        return None
    out = {
        "groups": [{"name": g, "share": _num(s * 100.0),
                    "unstable": bool(stab and g in stab.unstable_groups)} for g, s in v.ordered()],
        "idioKey": v.idio_key,
        "r2": _num(v.r2),
        "r2Adjusted": _num(v.r2_adjusted),
        "nFactors": v.n_factors,
        "members": {g: list(cols) for g, cols in v.groups.items()},
    }
    if stab is not None:
        out["stability"] = {
            "unstableGroups": list(stab.unstable_groups),
            "maxDelta": _num(stab.max_delta * 100.0),
            "threshold": _num(stab.threshold * 100.0),
            "perGroup": {g: {"long": _num(d["long"] * 100.0), "short": _num(d["short"] * 100.0),
                             "delta": _num(d["delta"] * 100.0)} for g, d in stab.per_group.items()},
        }
    return out


def _attribution_payload(attr: dict) -> dict:
    idio_key = attr["idio_key"]
    names = [k for k in attr["slices"] if k != idio_key] + [idio_key]
    return {
        "slices": [{"name": n, "pct": _num(attr["slices"][n] * 100.0)} for n in names],
        "idioKey": idio_key,
        "total": _num(attr["total"] * 100.0),
    }


def _gate_payload(result, ticker: str) -> dict:
    g = result.gates.get(ticker, {})
    size, fund, expo = g.get("size"), g.get("fund"), g.get("exposure")
    return {
        "size": None if not size else {"passed": size.passed, "note": size.note,
                                       "marketCap": _num(size.market_cap)},
        "fundamentals": None if not fund else {
            "overall": fund.overall,
            "basis": (g.get("fund_raw") or {}).get("basis"),   # flow-item basis: 'TTM->..' | 'FYxxxx'
            "industry": (g.get("fund_raw") or {}).get("industry"),  # Damodaran benchmark {name, source, ...}
            "metrics": {k: {"status": mv.status, "note": mv.note} for k, mv in fund.metrics.items()},
        },
        "exposure": None if not expo else {"status": expo.status, "note": expo.note},
    }


def _kill_risk_payload(kr) -> dict | None:
    if kr is None:
        return None
    return {"group": kr.group, "share": _num(kr.share), "factor": kr.factor, "beta": _num(kr.beta)}


def _signal_payload(sig) -> dict | None:
    if not sig:
        return None
    return {"window": sig["window"], "recentIdio": _num(sig["recentIdio"]),
            "recentSlopeAnn": _num(sig["recentSlopeAnn"]), "state": sig["state"]}


def _opportunity_payload(result) -> dict:
    """Factor-model opportunity read: per-stock buckets + threshold-gated trade ideas (directional
    longs, neutral pairs, factor-hedged book). All numbers COMPUTED — nothing fabricated; when nothing
    clears the bar, `none` is True and `message` says so honestly."""
    opp = build_opportunities(result)
    return {
        "none": bool(opp.none),
        "message": opp.message,
        "longs": list(opp.longs),
        "reads": [{
            "ticker": r.ticker, "bucket": r.bucket, "idio": _num(r.idio), "ir": _num(r.ir),
            "tstat": _num(r.tstat), "tier": r.tier, "raw": _num(r.raw), "r2": _num(r.r2),
            "noisy": bool(r.noisy), "qualifiesLong": bool(r.qualifies_long),
            "killRisk": _kill_risk_payload(r.kill_risk), "note": r.note,
            "signal": _signal_payload(r.signal),
        } for r in opp.reads],
        "pairs": [{
            "long": p.long, "short": p.short, "factor": p.factor,
            "hedgeRatio": _num(p.hedge_ratio), "cos": _num(p.cos),
            "longIdio": _num(p.long_idio), "shortIdio": _num(p.short_idio), "note": p.note,
        } for p in opp.pairs],
        "book": None if opp.book is None else {
            "longs": [{"ticker": l.ticker, "weight": _num(l.weight), "kind": l.kind,
                       "label": l.label} for l in opp.book.longs],
            "hedges": [{"ticker": h.ticker, "weight": _num(h.weight), "kind": h.kind,
                        "label": h.label} for h in opp.book.hedges],
            "unhedged": list(opp.book.unhedged), "note": opp.book.note,
        },
    }


def screen_payload(result, run_id: str = "", name: str = "") -> dict:
    """Full JSON payload for one run: config echo, colour-coded scorecard rows, per-stock detail,
    gates, skipped names, and data-quality caveats."""
    cfg = result.config
    scorecard = build_scorecard(result).to_dict(orient="records")
    order = sorted(result.outputs, key=lambda t: result.outputs[t].trend.rank_key, reverse=True)
    active = set(cfg.factor_logical)
    return {
        "runId": run_id,
        "name": name or run_id,
        "config": {
            "tickers": list(cfg.tickers),
            "equipmentTickers": list(getattr(cfg, "equipment_tickers", [])),
            "factorSet": cfg.factor_set,
            "factorLogical": cfg.factor_logical,
            "customDrivers": ([{"name": k, "ticker": v, "group": cfg.custom_groups.get(k, "")}
                               for k, v in cfg.custom_factors.items()]
                              if cfg.factor_set == "custom" else None),
            "horizon": cfg.time_horizon_days,
            "asOfDate": cfg.as_of_date.isoformat(),
        },
        "scorecard": scorecard,
        "opportunity": _opportunity_payload(result),
        "stocks": [_stock_payload(result.outputs[t], cfg.factor_map, cfg.custom_groups) for t in order],
        "gates": {t: _gate_payload(result, t) for t in cfg.tickers},
        "skipped": [{"ticker": t, "reason": why} for t, why in result.skipped],
        "caveats": {
            "oil": bool(active & {"oil", "gas"}),
            "brentCollinear": {"oil", "brent"} <= active,
            "driversMode": cfg.factor_set == "drivers",
            "driversModeCaveat": DRIVERS_MODE_CAVEAT if cfg.factor_set == "drivers" else None,
            "droppedFactors": list(getattr(result, "dropped_factors", [])),
        },
    }
