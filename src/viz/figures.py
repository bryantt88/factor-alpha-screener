"""Per-stock Plotly figure builders for the app (docs/OUTPUTS.md).

Returns go.Figure objects (for st.plotly_chart) rather than writing HTML — same colour language and
conventions as viz/charts.py (which writes the CLI's standalone HTML). One stock per figure, for the
dashboard's per-stock drill-down.
"""
from __future__ import annotations

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .charts import C_GAP, C_IDIO, C_RAW, FACTOR_COLORS


def fig_raw_vs_idio_single(o) -> go.Figure:
    r = o.reg
    raw = r.cum_raw_compounded * 100.0
    idio = r.cum_idio_compounded * 100.0
    x = list(raw.index)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=raw, name="raw return", line=dict(color=C_RAW, width=1.6)))
    fig.add_trace(go.Scatter(x=x, y=idio, name="idiosyncratic (α+ε)", fill="tonexty",
                             fillcolor=C_GAP, line=dict(color=C_IDIO, width=2.4)))
    fig.add_hline(y=0, line=dict(color="#888", width=0.8, dash="dot"))
    fig.add_annotation(x=x[-1], y=raw.iloc[-1], text=f"raw {raw.iloc[-1]:+.0f}%", showarrow=False,
                       xanchor="left", font=dict(color=C_RAW, size=11))
    fig.add_annotation(x=x[-1], y=idio.iloc[-1], text=f"α+ε {idio.iloc[-1]:+.0f}%", showarrow=False,
                       xanchor="left", font=dict(color=C_IDIO, size=11))
    fig.update_layout(template="plotly_white", height=360, margin=dict(l=10, r=76, t=52, b=56),
                      title=dict(text="Raw vs idiosyncratic (α+ε) — compounded; shaded gap = factor contribution",
                                 x=0, xanchor="left", y=0.98, yanchor="top", font=dict(size=13)),
                      yaxis_title="cumulative return (%)",
                      legend=dict(orientation="h", yanchor="top", y=-0.16, x=0))
    return fig


def fig_alpha_decomposition(o) -> go.Figure:
    """Signal vs noise: the cumulative idiosyncratic path (α+ε) against the pure persistent-drift
    line (α only). A near-straight idio hugging the α line = steady, real alpha; a jumpy idio far
    from a flat α line = noise / one-off moves (own return, but no proven alpha)."""
    r = o.reg
    idio = r.cum_idio_compounded * 100.0
    drift = r.cum_alpha_drift * 100.0
    x = list(idio.index)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=idio, name="idiosyncratic (α+ε)", line=dict(color=C_IDIO, width=2.2)))
    fig.add_trace(go.Scatter(x=x, y=drift, name="persistent drift (α only)",
                             line=dict(color="#4F46E5", width=2, dash="dash")))
    fig.add_hline(y=0, line=dict(color="#888", width=0.8, dash="dot"))
    tr = o.trend
    verdict = ("✓ statistically real alpha" if tr.alpha_significant
               else ("⚠ not significant — noise-driven" if tr.alpha_annualized > 0 else "✗ no positive alpha"))
    fig.add_annotation(x=x[0], y=max(idio.max(), drift.max()), xanchor="left", yanchor="top",
                       showarrow=False, align="left", font=dict(size=11),
                       bgcolor="rgba(255,255,255,0.75)",
                       text=f"α {tr.alpha_annualized:+.0%}/yr · t {tr.alpha_tstat:+.1f} · "
                            f"p {tr.alpha_pvalue:.3f} · IR {tr.information_ratio:.2f}<br>{verdict}")
    fig.update_layout(template="plotly_white", height=360, margin=dict(l=10, r=76, t=52, b=56),
                      title=dict(text="Alpha vs noise — steady drift (dashed) vs the full idiosyncratic path",
                                 x=0, xanchor="left", y=0.98, yanchor="top", font=dict(size=13)),
                      yaxis_title="cumulative return (%)",
                      legend=dict(orientation="h", yanchor="top", y=-0.16, x=0))
    return fig


def fig_regression_fit(o) -> go.Figure:
    """The linear regression itself: model-predicted vs actual daily return + the 45° fit line."""
    r = o.reg
    pred = (r.predicted * 100.0)
    actual = (r.stock_returns * 100.0)
    lo = float(min(pred.min(), actual.min()))
    hi = float(max(pred.max(), actual.max()))
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pred, y=actual, mode="markers", name="days",
                             marker=dict(color=C_IDIO, size=5, opacity=0.55)))
    fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", name="perfect fit (y=x)",
                             line=dict(color="#888", width=1, dash="dash")))
    betas = "  ".join(f"β_{f} {b:+.2f}" for f, b in r.betas.items())
    fig.add_annotation(x=lo, y=hi, xanchor="left", yanchor="top", showarrow=False,
                       align="left", font=dict(size=11), bgcolor="rgba(255,255,255,0.75)",
                       text=f"R² = {r.r2:.2f}   α(daily) = {r.alpha:+.4f}<br>{betas}")
    fig.update_layout(template="plotly_white", height=360, margin=dict(l=10, r=10, t=52, b=64),
                      title=dict(text="Linear regression fit — predicted vs actual daily return (%)",
                                 x=0, xanchor="left", y=0.98, yanchor="top", font=dict(size=13)),
                      xaxis_title="model-predicted daily return (%)",
                      yaxis_title="actual daily return (%)",
                      legend=dict(orientation="h", yanchor="top", y=-0.22, x=0))
    return fig


def fig_rolling_single(o) -> go.Figure:
    rc, rb = o.roll_corr, o.roll_beta
    hc = getattr(o, "headline_corr", {}) or {}
    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=("rolling correlation (60d)", "rolling beta (90d)"),
                        horizontal_spacing=0.1)
    for c in rc.columns:
        col = FACTOR_COLORS.get(c)
        fig.add_trace(go.Scatter(x=list(rc.index), y=rc[c], name=c, legendgroup=c,
                                 line=dict(color=col)), row=1, col=1)
        fig.add_trace(go.Scatter(x=list(rb.index), y=rb[c], name=c, legendgroup=c,
                                 line=dict(color=col), showlegend=False), row=1, col=2)
        # dotted reference = the static full-year (univariate) value — the "actual" number
        if c in hc:
            fig.add_hline(y=hc[c]["corr"], line=dict(color=col, width=1, dash="dot"), row=1, col=1,
                          annotation_text=f"1y ρ {hc[c]['corr']:+.2f}", annotation_position="top left",
                          annotation_font=dict(color=col, size=10))
            fig.add_hline(y=hc[c]["beta"], line=dict(color=col, width=1, dash="dot"), row=1, col=2,
                          annotation_text=f"1y β {hc[c]['beta']:+.2f}", annotation_position="top left",
                          annotation_font=dict(color=col, size=10))
    fig.add_hline(y=0, line=dict(color="#888", width=0.6, dash="dot"), row=1, col=1)
    fig.add_hline(y=0, line=dict(color="#888", width=0.6, dash="dot"), row=1, col=2)
    fig.update_yaxes(range=[-1, 1], row=1, col=1)
    # No main title (the tab label + caption below cover it) so it can't collide with the two subplot
    # titles; legend sits below the panels. Univariate, per commodity; dotted = static 1-yr value.
    fig.update_layout(template="plotly_white", height=340, margin=dict(l=10, r=10, t=46, b=56),
                      legend=dict(orientation="h", yanchor="top", y=-0.16, x=0))
    return fig


_ATTR_LABEL = {"market": "Market", "rates": "Rates", "oil": "Oil", "gas": "Gas"}


def fig_attribution_single(o) -> go.Figure:
    attr = o.attr
    idio_key = attr["idio_key"]
    names = [k for k in attr["slices"] if k != idio_key] + [idio_key]
    vals = [attr["slices"][k] * 100.0 for k in names]
    total = attr["total"] * 100.0
    disp = [_ATTR_LABEL.get(n, "Own (α+ε)" if n == idio_key else n) for n in names] + ["Total"]
    ys = vals + [total]
    # data labels on every bar: signed % points contributed to the total return
    labels = [f"{v:+.1f}%" for v in vals] + [f"{total:+.1f}%"]
    fig = go.Figure(go.Waterfall(
        x=disp, measure=["relative"] * len(names) + ["total"], y=ys,
        text=labels, textposition="outside", textfont=dict(size=11),
        connector=dict(line=dict(color="rgba(0,0,0,0.3)")),
        decreasing=dict(marker=dict(color="#C8795A")),
        increasing=dict(marker=dict(color="#6FB68A")),
        totals=dict(marker=dict(color="#4F46E5"))))
    pad = max(abs(min(ys)), abs(max(ys))) * 0.22 + 2
    fig.update_yaxes(range=[min(0, min(ys)) - pad, max(0, max(ys)) + pad])
    fig.update_layout(template="plotly_white", height=340, margin=dict(l=10, r=10, t=52, b=20),
                      title=dict(text="Return attribution — how each factor added to / subtracted from "
                                      "the total (percentage points)", x=0, xanchor="left", y=0.98,
                                 yanchor="top", font=dict(size=13)),
                      yaxis_title="contribution (pts)", showlegend=False, uniformtext_minsize=9,
                      uniformtext_mode="hide")
    return fig


def fig_relative_strength(rel, ticker: str, benchmark: str) -> go.Figure:
    """Output 4 — cumulative excess return of the stock vs its sector benchmark."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(rel.index), y=rel, name=f"{ticker} − {benchmark}",
                             line=dict(color=C_IDIO, width=2.2)))
    fig.add_hline(y=0, line=dict(color="#888", width=0.8, dash="dot"))
    end = rel.iloc[-1]
    fig.add_annotation(x=list(rel.index)[-1], y=end, text=f"{end:+.0f} pts vs {benchmark}",
                       showarrow=False, xanchor="left", font=dict(color=C_IDIO, size=11))
    fig.update_layout(template="plotly_white", height=300, margin=dict(l=10, r=70, t=40, b=10),
                      title=f"Relative strength vs {benchmark} — rising = beating the sector",
                      yaxis_title="cumulative excess return (pts)")
    return fig


def fig_combined_idio(outputs: dict) -> go.Figure:
    fig = go.Figure()
    for t, o in outputs.items():
        idio = o.reg.cum_idio_compounded * 100.0
        fig.add_trace(go.Scatter(x=list(idio.index), y=idio, name=t, mode="lines"))
    fig.add_hline(y=0, line=dict(color="#888", width=0.8, dash="dot"))
    fig.update_layout(template="plotly_white", height=460, margin=dict(l=10, r=10, t=40, b=10),
                      title="Combined idiosyncratic (α+ε) — ranking view",
                      yaxis_title="cumulative idiosyncratic return (%)")
    return fig
