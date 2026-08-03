"""The five outputs as annotated, interactive Plotly charts (docs/OUTPUTS.md).

Built to READ: shaded raw-vs-idio gap, annotated endpoints, Track tags, one-line verdicts, and a
consistent colour language (idiosyncratic/alpha+epsilon = one fixed colour; each factor fixed; raw
price neutral). Charts are written as interactive HTML with a shared local plotly.min.js
(include_plotlyjs="directory"), so they render offline.

Step 1 ships Outputs 1-3 + the regression-detail table (partial Output 5). Charts consume the
per-ticker `StockOutput` objects assembled in src/main.py (accessed by attribute — no import cycle).
"""
from __future__ import annotations

import os

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- consistent colour language ---
C_IDIO = "#2ca02c"      # idiosyncratic (alpha + epsilon) — the stock's own contribution
C_RAW = "#7f7f7f"       # raw price — neutral
C_GAP = "rgba(127,127,127,0.15)"
FACTOR_COLORS = {
    "market": "#1f77b4",
    "rates": "#9467bd",
    "oil": "#8c564b",
    "brent": "#a0522d",
    "gas": "#ff7f0e",
}
# Driver-group colours for the Performance-Drivers variance bar (idiosyncratic reuses C_IDIO).
GROUP_COLORS = {
    "Market": "#1f77b4",
    "Rates": "#9467bd",
    "Energy": "#8c564b",
    "Sector": "#17becf",
    "Macro": "#e377c2",
    "Style": "#ff7f0e",
    "Idiosyncratic": C_IDIO,
}
_HTML_KW = dict(include_plotlyjs="directory", full_html=True)


def _save(fig: go.Figure, out_dir: str, name: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    fig.write_html(path, **_HTML_KW)
    return path


# ---------------------------------------------------------------------------
# Output 1 — raw vs idiosyncratic trend
# ---------------------------------------------------------------------------
def chart_raw_vs_idiosyncratic(outputs: dict, out_dir: str) -> list[str]:
    tickers = list(outputs)
    n = len(tickers)
    titles = [f"{t} — {outputs[t].trend.track_tag}" for t in tickers]
    fig = make_subplots(rows=n, cols=1, subplot_titles=titles, vertical_spacing=max(0.05, 0.18 / n))

    for i, t in enumerate(tickers, start=1):
        r = outputs[t].reg
        raw = r.cum_raw_compounded * 100.0
        idio = r.cum_idio_compounded * 100.0
        x = list(raw.index)
        showleg = i == 1
        # raw first, then idio with fill between the two (the factor-contribution gap)
        fig.add_trace(go.Scatter(x=x, y=raw, name="raw return", legendgroup="raw",
                                 line=dict(color=C_RAW, width=1.6), showlegend=showleg), row=i, col=1)
        fig.add_trace(go.Scatter(x=x, y=idio, name="idiosyncratic (α+ε)", legendgroup="idio",
                                 line=dict(color=C_IDIO, width=2.2), fill="tonexty", fillcolor=C_GAP,
                                 showlegend=showleg), row=i, col=1)
        fig.add_hline(y=0, line=dict(color="black", width=0.8, dash="dot"), row=i, col=1)
        # endpoint annotations
        fig.add_annotation(x=x[-1], y=raw.iloc[-1], text=f"raw {raw.iloc[-1]:+.0f}%",
                           showarrow=False, xanchor="left", font=dict(color=C_RAW, size=11), row=i, col=1)
        fig.add_annotation(x=x[-1], y=idio.iloc[-1], text=f"α+ε {idio.iloc[-1]:+.0f}%",
                           showarrow=False, xanchor="left", font=dict(color=C_IDIO, size=11), row=i, col=1)
        fig.update_yaxes(title_text="cum. return (%)", row=i, col=1)

    fig.update_layout(height=320 * n, template="plotly_white",
                      title="Raw vs idiosyncratic (α+ε) trend — gap shaded = explained by factors",
                      legend=dict(orientation="h", y=1.02, x=0))
    paths = [_save(fig, out_dir, "1_raw_vs_idiosyncratic.html")]

    # combined idiosyncratic ranking chart
    comb = go.Figure()
    for t in tickers:
        idio = outputs[t].reg.cum_idio_compounded * 100.0
        comb.add_trace(go.Scatter(x=list(idio.index), y=idio, name=t, mode="lines"))
    comb.add_hline(y=0, line=dict(color="black", width=0.8, dash="dot"))
    comb.update_layout(height=520, template="plotly_white",
                       title="Combined idiosyncratic (α+ε) trend — ranking view",
                       yaxis_title="cumulative idiosyncratic return (%)")
    paths.append(_save(comb, out_dir, "1b_combined_idiosyncratic.html"))
    return paths


# ---------------------------------------------------------------------------
# Performance Drivers — variance decomposition bar (the v2 JPM-style panel)
# ---------------------------------------------------------------------------
def chart_variance_drivers(outputs: dict, out_dir: str) -> list[str]:
    """Horizontal variance-share bar per stock (Market / Rates / Energy / … / Idiosyncratic),
    matching the JPM 'Performance Drivers' panel. Shares sum to 100%; idiosyncratic = 1 − R²."""
    tickers = [t for t in outputs if outputs[t].variance is not None]
    if not tickers:
        return []
    n = len(tickers)
    titles = [f"{t} — {outputs[t].variance.r2_adjusted:.0%} explained (adj R²), "
              f"{outputs[t].variance.shares[outputs[t].variance.idio_key]:.0%} idiosyncratic"
              for t in tickers]
    fig = make_subplots(rows=n, cols=1, subplot_titles=titles, vertical_spacing=max(0.05, 0.18 / n))

    for i, t in enumerate(tickers, start=1):
        v = outputs[t].variance
        items = v.ordered()                      # factor groups (desc) then Idiosyncratic last
        names = [g for g, _ in items][::-1]      # reversed so Idiosyncratic sits at the BOTTOM
        vals = [s * 100.0 for _, s in items][::-1]
        colors = [GROUP_COLORS.get(g, "#888888") for g in names]
        fig.add_trace(
            go.Bar(x=vals, y=names, orientation="h", marker=dict(color=colors),
                   text=[f"{x:.0f}%" for x in vals], textposition="outside",
                   cliponaxis=False, showlegend=False),
            row=i, col=1)
        fig.update_xaxes(range=[0, max(vals) * 1.18], title_text="share of return variance (%)",
                         row=i, col=1)

    fig.update_layout(height=max(220, 90 * max(1, len(GROUP_COLORS))) if n == 1 else 260 * n,
                      template="plotly_white",
                      title="Performance Drivers — share of return variance per driver group "
                            "(idiosyncratic = 1 − R² = the stock's own story)")
    return [_save(fig, out_dir, "1c_performance_drivers.html")]


# ---------------------------------------------------------------------------
# Output 2 — rolling correlation + rolling beta (decoupling)
# ---------------------------------------------------------------------------
def chart_rolling_decoupling(outputs: dict, out_dir: str) -> list[str]:
    tickers = list(outputs)
    n = len(tickers)
    titles = []
    for t in tickers:
        titles += [f"{t} — rolling correlation", f"{t} — rolling beta"]
    fig = make_subplots(rows=n, cols=2, subplot_titles=titles, horizontal_spacing=0.09,
                        vertical_spacing=max(0.06, 0.2 / n))

    for i, t in enumerate(tickers, start=1):
        rc = outputs[t].roll_corr
        rb = outputs[t].roll_beta
        showleg = i == 1
        for c in rc.columns:
            col = FACTOR_COLORS.get(c, None)
            fig.add_trace(go.Scatter(x=list(rc.index), y=rc[c], name=c, legendgroup=c,
                                     line=dict(color=col), showlegend=showleg), row=i, col=1)
            fig.add_trace(go.Scatter(x=list(rb.index), y=rb[c], name=c, legendgroup=c,
                                     line=dict(color=col), showlegend=False), row=i, col=2)
        fig.add_hline(y=0, line=dict(color="black", width=0.6, dash="dot"), row=i, col=1)
        fig.add_hline(y=0, line=dict(color="black", width=0.6, dash="dot"), row=i, col=2)
        fig.update_yaxes(range=[-1, 1], title_text="corr", row=i, col=1)
        fig.update_yaxes(title_text="beta", row=i, col=2)

    fig.update_layout(height=300 * n, template="plotly_white",
                      title="Rolling correlation & beta to oil/gas — a falling line = decoupling",
                      legend=dict(orientation="h", y=1.02, x=0))
    return [_save(fig, out_dir, "2_rolling_decoupling.html")]


# ---------------------------------------------------------------------------
# Output 3 — return attribution waterfall
# ---------------------------------------------------------------------------
def chart_attribution_waterfall(outputs: dict, out_dir: str) -> list[str]:
    tickers = list(outputs)
    n = len(tickers)
    fig = make_subplots(rows=n, cols=1, subplot_titles=list(tickers),
                        vertical_spacing=max(0.06, 0.2 / n))
    for i, t in enumerate(tickers, start=1):
        attr = outputs[t].attr
        idio_key = attr["idio_key"]
        # order: factor slices, then idiosyncratic, then total
        names = [k for k in attr["slices"] if k != idio_key] + [idio_key]
        vals = [attr["slices"][k] * 100.0 for k in names]
        measures = ["relative"] * len(names) + ["total"]
        names_disp = names + ["total"]
        vals_disp = vals + [attr["total"] * 100.0]
        fig.add_trace(
            go.Waterfall(x=names_disp, y=vals_disp, measure=measures,
                         connector=dict(line=dict(color="rgba(0,0,0,0.3)")),
                         decreasing=dict(marker=dict(color="#d62728")),
                         increasing=dict(marker=dict(color="#1f77b4")),
                         totals=dict(marker=dict(color="#555555"))),
            row=i, col=1)
        fig.update_yaxes(title_text="contribution (%)", row=i, col=1)
    fig.update_layout(height=340 * n, template="plotly_white", showlegend=False,
                      title="Return attribution — factor slices vs the stock's own (α+ε) contribution")
    return [_save(fig, out_dir, "3_attribution_waterfall.html")]


# ---------------------------------------------------------------------------
# Partial Output 5 — regression-detail table
# ---------------------------------------------------------------------------
def build_detail_table(outputs: dict) -> pd.DataFrame:
    rows = []
    for t, o in outputs.items():
        r, tr = o.reg, o.trend
        row = {
            "ticker": t,
            "track": tr.track_tag.split(" — ")[0],
            "idio α+ε (cum)": f"{tr.idio_endpoint:+.1%}",
            "raw 12m": f"{o.raw_12m:+.1%}" if o.raw_12m is not None else "n/a",
            "raw 6m": f"{o.raw_6m:+.1%}" if o.raw_6m is not None else "n/a",
            "α (ann.)": f"{r.alpha_annualized:+.1%}",
            "R²": f"{r.r2:.2f}",
        }
        for f, b in r.betas.items():
            row[f"β_{f}"] = f"{b:+.2f}"
            row[f"p_{f}"] = f"{r.pvalues.get(f, float('nan')):.2f}"
        for c, d in o.headline_corr.items():
            row[f"corr_{c}(1y)"] = f"{d['corr']:+.2f}"
        rows.append(row)
    df = pd.DataFrame(rows)
    # sort by cumulative idiosyncratic (descending) — parse back the numeric endpoint
    order = sorted(outputs, key=lambda t: outputs[t].trend.idio_endpoint, reverse=True)
    df["__k"] = df["ticker"].map({t: i for i, t in enumerate(order)})
    df = df.sort_values("__k").drop(columns="__k").reset_index(drop=True)
    return df


def save_detail_table(outputs: dict, out_dir: str) -> str:
    df = build_detail_table(outputs)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "5_scorecard_detail.html")
    html = ["<meta charset='utf-8'><style>",
            "body{font-family:system-ui,Segoe UI,Arial;margin:24px}",
            "table{border-collapse:collapse}th,td{border:1px solid #ddd;padding:6px 10px;font-size:13px;text-align:right}",
            "th{background:#f4f4f4}td:first-child,th:first-child{text-align:left}",
            "h2{font-weight:600}</style>",
            "<h2>Regression-detail scorecard (Step 1) — sorted by cumulative idiosyncratic α+ε</h2>",
            df.to_html(index=False, escape=False),
            "<p style='color:#666;font-size:12px'>Gates 1–3 (size, fundamentals, AI exposure) arrive in later build steps. "
            "Idiosyncratic = α+ε; correlations are the static full-window (last-year) figure.</p>"]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(html))
    return path


# ---------------------------------------------------------------------------
# Full scorecard (Output 5) — every ticker, all gates + regression detail
# ---------------------------------------------------------------------------
_STATUS_GLYPH = {"pass": "✓", "fail": "✗", "flag": "⚠", "unverified": "?", "pending": "…"}


def _glyph(status: str) -> str:
    return _STATUS_GLYPH.get(status, "?")


def _bool_glyph(b) -> str:
    return "✓" if b is True else ("✗" if b is False else "?")


def _alpha_sig_glyph(tr) -> str:
    """✓ = statistically real positive alpha; ⚠ = positive but noise-driven (not significant);
    ✗ = no positive alpha. Mirrors the verdict colour language."""
    if tr.alpha_significant:
        return "✓"
    if tr.alpha_annualized > 0:
        return "⚠"
    return "✗"


def build_scorecard(result) -> pd.DataFrame:
    """One row per input ticker: Gates 1-2 (+3 placeholder) + Gate-4 regression detail.

    Scorecard, not funnel — every ticker appears, including those with no regression (shown 'no-reg').
    Sorted by cumulative idiosyncratic α+ε (regression names first, descending)."""
    cfg = result.config
    rows = []
    for t in cfg.tickers:
        g = result.gates.get(t, {})
        size = g.get("size")
        fund = g.get("fund")
        expo = g.get("exposure")
        o = result.outputs.get(t)

        def mnote(key):
            if not fund or key not in fund.metrics:
                return "?"
            mv = fund.metrics[key]
            return f"{_glyph(mv.status)} {mv.note}"

        row = {
            "ticker": t,
            "G1": _bool_glyph(size.passed) if size else "?",
            "market cap": f"${size.market_cap/1e9:.1f}B" if (size and size.market_cap) else "n/a",
            "G2": _glyph(fund.overall) if fund else "?",
            "EBITDA margin": mnote("ebitda_margin"),
            "net debt/EBITDA": mnote("net_debt_to_ebitda"),
            "EPS surprise": mnote("earnings_surprise"),
            "EV/EBITDA": mnote("valuation"),
            "G3": _glyph(expo.status) if expo else "—",  # AI-exposure (propose-and-approve)
        }
        if o:
            tr, reg = o.trend, o.reg
            idio_cell = f"{tr.idio_endpoint:+.1%}"
            if tr.tracking_noise:                 # oil-factor tracking-noise risk (read w/ R²)
                idio_cell += " ⚠"
            row.update({
                "G4": _bool_glyph(tr.passed),
                "α sig?": _alpha_sig_glyph(tr),   # is the own-merit drift statistically real?
                "α (ann.)": f"{tr.alpha_annualized:+.1%}",
                "α t-stat": f"{tr.alpha_tstat:+.2f}",
                "info ratio": f"{tr.information_ratio:.2f}",
                "idio α+ε": idio_cell,
                "raw 12m": f"{o.raw_12m:+.1%}" if o.raw_12m is not None else "n/a",
                "R²": f"{reg.r2:.2f}",
            })
            for f in reg.betas:                            # model (partial, multivariate) betas
                row[f"β_{f}"] = f"{reg.betas[f]:+.2f}"
            row["track"] = tr.track_tag.split(" — ")[0]
        else:
            row.update({"G4": "?", "α sig?": "?", "α (ann.)": "n/a", "α t-stat": "n/a",
                        "info ratio": "n/a", "idio α+ε": "n/a", "raw 12m": "n/a", "R²": "n/a"})
            for f in cfg.factor_logical:
                row[f"β_{f}"] = "n/a"
            row["track"] = "equipment" if t.upper() in {e.upper() for e in cfg.equipment_tickers} else "no-reg"
        rows.append(row)

    df = pd.DataFrame(rows)
    # rank by risk-adjusted alpha (information ratio) — the #3 enhancement, not just "did it go up"
    rk = {t: (result.outputs[t].trend.rank_key if t in result.outputs else float("-inf"))
          for t in cfg.tickers}
    df["__k"] = df["ticker"].map(lambda t: -rk[t])
    return df.sort_values("__k").drop(columns="__k").reset_index(drop=True)


# --- verdict colour language (shared by the styled scorecard; matches the UI token system) --------
_VERDICT_CSS = {
    "pass":    "background-color:#DCFCE7;color:#166534;",   # green  — pass / Track 1
    "flag":    "background-color:#FEF3C7;color:#92400E;",   # amber  — flag / Track 2 / noise
    "fail":    "background-color:#FEE2E2;color:#991B1B;",   # red    — fail / Reject
    "neutral": "background-color:#F1F5F9;color:#475569;",   # slate  — unverified / no trend
}


def _verdict_of(val) -> str:
    """Map a scorecard cell's leading glyph / track word to a verdict colour bucket."""
    s = str(val).strip()
    if s.startswith("✓") or s.startswith("Rising on its own"):
        return "pass"
    if s.startswith("✗") or s.startswith("Just riding the wave"):
        return "fail"
    if s.startswith("⚠") or ("⚠" in s) or s.startswith("Turning up underneath"):
        return "flag"
    if s.startswith(("?", "…", "—", "n/a", "No clear", "no-reg")):
        return "neutral"
    return ""


def style_scorecard(df: pd.DataFrame):
    """Return a colour-coded pandas Styler for the scorecard (verdict cells + track tags).

    Colours only the verdict-bearing cells (gates, metric notes, track, α+ε flag); numeric columns
    are left clean for the monospaced/tabular treatment the UI applies via CSS. Version-safe across
    the pandas Styler.map / .applymap rename."""
    def _css(val):
        return _VERDICT_CSS.get(_verdict_of(val), "")

    sty = df.style
    elementwise = getattr(sty, "map", None) or sty.applymap   # pandas >=2.1 uses .map
    sty = elementwise(_css)
    sty = sty.set_properties(subset=["ticker"], **{"font-weight": "700"})
    return sty.hide(axis="index")
