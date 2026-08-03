"""AI-Power Stack Screener — Streamlit platform (docs/PLATFORM.md).

Three pages: New Run, Results Dashboard, History/KB. The UI is a thin convenience layer — it calls
the exact same `run_screen()` the CLI uses (no reimplementation). All four gates are live (size,
fundamentals, AI-exposure agent, idiosyncratic regression); the optional per-stock "How to read (ask
Gemini)" button sends the already-computed numbers to the gemini CLI ($0 backend) for a plain-language
read — it never invents a figure.

Design language (v1.1): a disciplined research-terminal look — verdict colour is meaning (green =
pass / Track 1, amber = flag / Track 2, red = fail / Reject, slate = unverified), numbers are set in a
tabular monospace, and the palette is otherwise quiet so the scorecard reads at a glance. All styling
is offline-safe (no external fonts/CDN), matching the offline-first charts.

Run:  streamlit run src/app/ui.py
"""
from __future__ import annotations

import os
import sys

# make `import src.*` work under `streamlit run` (script is executed, not imported as a package)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)  # so config.yaml and runs/ resolve relative to the repo root

import streamlit as st

from src.agent.exposure_agent import TYPES, confirm_exposure
from src.agent.gemini_client import GeminiAuthError, GeminiError, gemini_available
from src.app.explain import explain_stock
from src.config import load_config
from src.data.benchmark import benchmark_for_type, relative_strength
from src.gates.exposure import exposure_verdict
from src.gates.trend import (BRENT_COLLINEARITY_CAVEAT, OIL_FACTOR_CAVEAT,
                             combined_oil_beta)
from src.knowledge_base import hashing, store
from src.main import run_screen
from src.viz.charts import build_scorecard, style_scorecard
from src.viz.figures import (fig_alpha_decomposition, fig_attribution_single,
                             fig_combined_idio, fig_raw_vs_idio_single, fig_regression_fit,
                             fig_relative_strength, fig_rolling_single)

PAGES = ["① New Run", "② Results", "③ History"]
st.set_page_config(page_title="AI-Power Stack Screener", page_icon="⚡", layout="wide")


# --------------------------------------------------------------------------- theme
_THEME_CSS = """
<style>
:root{
  --ink:#0F172A; --muted:#64748B; --faint:#94A3B8;
  --canvas:#F6F7F9; --card:#FFFFFF; --border:#E2E8F0;
  --accent:#4F46E5; --accent-2:#06B6D4;
  --mono:"SF Mono",ui-monospace,"Cascadia Code","JetBrains Mono",Consolas,Menlo,monospace;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
.stApp{ background:var(--canvas); }
html, body, [class*="css"]{ font-family:var(--sans); color:var(--ink); }
.block-container{ padding-top:2.2rem; padding-bottom:4rem; max-width:1180px; }

/* --- headings --- */
h1,h2,h3{ color:var(--ink); letter-spacing:-.01em; font-weight:700; }
h2{ font-size:1.35rem; margin-top:.4rem; }
h3{ font-size:1.08rem; }

/* --- header banner (signature: thin voltage rule) --- */
.apx-hero{ margin:0 0 1.4rem 0; }
.apx-hero .row{ display:flex; align-items:baseline; gap:.6rem; }
.apx-hero .mark{ font-size:1.5rem; }
.apx-hero .name{ font-size:1.5rem; font-weight:800; letter-spacing:-.02em; }
.apx-hero .sub{ color:var(--muted); font-size:.95rem; margin-top:.2rem; }
.apx-rule{ height:3px; border-radius:3px; margin:.7rem 0 0 0; width:100%;
  background:linear-gradient(90deg,#4F46E5 0%,#6366F1 45%,#06B6D4 100%); }

/* --- eyebrow / section label --- */
.apx-eyebrow{ text-transform:uppercase; letter-spacing:.14em; font-size:.72rem;
  font-weight:700; color:var(--faint); margin:1.4rem 0 .5rem 0; }

/* --- verdict pill --- */
.apx-pill{ display:inline-block; padding:.16rem .6rem; border-radius:999px;
  font-size:.78rem; font-weight:700; letter-spacing:.01em; }
.apx-pass{ background:#DCFCE7; color:#166534; }
.apx-flag{ background:#FEF3C7; color:#92400E; }
.apx-fail{ background:#FEE2E2; color:#991B1B; }
.apx-neutral{ background:#F1F5F9; color:#475569; }

/* --- metric cards --- */
[data-testid="stMetric"]{ background:var(--card); border:1px solid var(--border);
  border-radius:12px; padding:.85rem 1rem; box-shadow:0 1px 2px rgba(15,23,42,.04); }
[data-testid="stMetricValue"]{ font-family:var(--mono); font-weight:700; letter-spacing:-.02em;
  font-variant-numeric:tabular-nums; }
[data-testid="stMetricLabel"]{ text-transform:uppercase; letter-spacing:.08em;
  font-size:.68rem !important; color:var(--muted); font-weight:700; }

/* --- dataframe: tabular numerals so columns line up --- */
[data-testid="stDataFrame"] *{ font-family:var(--mono) !important;
  font-variant-numeric:tabular-nums; }
[data-testid="stDataFrame"]{ border:1px solid var(--border); border-radius:12px; overflow:hidden; }

/* --- sidebar --- */
[data-testid="stSidebar"]{ background:var(--card); border-right:1px solid var(--border); }
[data-testid="stSidebar"] .apx-brand{ font-weight:800; font-size:1.05rem; letter-spacing:-.01em; }

/* --- buttons --- */
.stButton>button{ border-radius:9px; font-weight:600; border:1px solid var(--border); }
.stButton>button[kind="primary"]{ background:var(--accent); border-color:var(--accent); }
.stButton>button[kind="primary"]:hover{ background:#4338CA; border-color:#4338CA; }

/* --- expanders --- */
[data-testid="stExpander"]{ border:1px solid var(--border); border-radius:12px;
  background:var(--card); box-shadow:0 1px 2px rgba(15,23,42,.03); }
[data-testid="stExpander"] summary{ font-weight:600; }

/* --- tabs --- */
[data-baseweb="tab-list"]{ gap:.2rem; border-bottom:1px solid var(--border); }
[data-baseweb="tab"]{ font-weight:600; }
</style>
"""


def _inject_theme() -> None:
    st.markdown(_THEME_CSS, unsafe_allow_html=True)


def _hero(name: str, subtitle: str) -> None:
    st.markdown(
        f"<div class='apx-hero'><div class='row'><span class='mark'>⚡</span>"
        f"<span class='name'>{name}</span></div>"
        f"<div class='sub'>{subtitle}</div><div class='apx-rule'></div></div>",
        unsafe_allow_html=True)


def _eyebrow(text: str) -> None:
    st.markdown(f"<div class='apx-eyebrow'>{text}</div>", unsafe_allow_html=True)


# track / verdict -> pill class
_TRACK_PILL = {"Track 1": "apx-pass", "Track 2": "apx-flag", "Reject": "apx-fail"}


def _pill(text: str, cls: str) -> str:
    return f"<span class='apx-pill {cls}'>{text}</span>"


def _track_pill(track_tag: str) -> str:
    head = track_tag.split(" — ")[0]
    return _pill(track_tag, _TRACK_PILL.get(head, "apx-neutral"))


# --------------------------------------------------------------------------- helpers
def _parse_tickers(raw: str) -> list[str]:
    seen, out = set(), []
    for tok in raw.replace(",", " ").split():
        t = tok.strip().upper()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _go(page: str) -> None:
    st.session_state.nav = page
    st.rerun()


_GLYPH = {"pass": "✓", "fail": "✗", "flag": "⚠", "unverified": "?"}


def _bool_glyph(b) -> str:
    return "✓" if b is True else ("✗" if b is False else "?")


# --------------------------------------------------------------------------- sidebar
_inject_theme()
st.sidebar.markdown("<div class='apx-brand'>⚡ AI-Power Screener</div>", unsafe_allow_html=True)
st.sidebar.caption("Idiosyncratic-alpha screener for AI-power-stack equities")
page = st.sidebar.radio("Navigate", PAGES, key="nav")
st.sidebar.divider()
if gemini_available():
    st.sidebar.caption("🟢 Gemini CLI detected — 'How to read' explainer available")
else:
    st.sidebar.caption("⚪ Gemini CLI not found — explainer disabled")


# --------------------------------------------------------------------------- New Run
def page_new_run() -> None:
    _hero("New run", "Paste tickers, choose the factor mode, and run. Every ticker is scored — nothing is dropped.")
    with st.form("run_form"):
        raw = st.text_input("Tickers", value="CEG VST NRG VRT ETN",
                             help="Space- or comma-separated, e.g. CEG VST NRG VRT ETN")
        run_name = st.text_input("Run name (optional)", value="",
                                 help="A label to find this run later in History, e.g. "
                                      "'AI-power core — Jul 2026'. Defaults to the auto ID.")
        c1, c2 = st.columns(2)
        factor_set = c1.radio("Factor mode", ["4factor", "commodity", "boss"], horizontal=True,
                              help="4factor = market+rates+oil+gas · commodity = oil+gas only · "
                                   "boss = market+WTI+Brent+Henry Hub (the boss's literal spec).")
        horizon = c2.slider("Horizon (trading days)", 63, 504, 252, step=21,
                            help="Primary beta + residual window. 252 ≈ 12 months.")
        equip_raw = st.text_input(
            "Equipment names (fundamentals only — no regression)", value="",
            help="Boss: energy-equipment makers are screened on fundamentals, not the regression. "
                 "Space- or comma-separated, e.g. ETN VRT.")
        with st.expander("Advanced"):
            a1, a2 = st.columns(2)
            size_floor_b = a1.number_input("Size floor (Gate 1, $B)", min_value=0.0, value=2.0,
                                           step=0.5, help="Market cap ≥ this passes Gate 1.")
            fund_source = a2.selectbox("Fundamentals source (Gate 2)", ["public", "refinitiv"],
                                       help="public = best-effort yfinance; refinitiv = cached CSV.")
        submitted = st.form_submit_button("Run screen", type="primary")

    if submitted:
        tickers = _parse_tickers(raw)
        if not tickers:
            st.error("Enter at least one ticker.")
            return
        cfg = load_config("config.yaml", tickers=tickers, factor_set=factor_set, horizon=horizon,
                          fundamentals_source=fund_source, size_floor_usd=size_floor_b * 1e9,
                          equipment_tickers=_parse_tickers(equip_raw))
        dropped = sorted(set(tickers) - set(cfg.tickers))
        if dropped:
            st.info(f"Excluded (existing position / not covered): {', '.join(dropped)}")
        run_id = hashing.compute_run_id(cfg.tickers, cfg.factor_set, cfg.return_frequency,
                                        cfg.time_horizon_days, cfg.as_of_date)
        cfg.output_dir = os.path.join("runs", run_id)
        with st.spinner(f"Pulling prices and running the regression on {len(tickers)} ticker(s)…"):
            result = run_screen(cfg, make_charts=False)   # charts written only on KB save (opt-in)
        st.session_state.result = result
        st.session_state.run_id = run_id
        st.session_state.run_name = run_name
        st.session_state.saved = False                    # not persisted until user opts in
        n_ok, n_skip = len(result.outputs), len(result.skipped)
        st.success(f"Done — {n_ok} scored, {n_skip} skipped. Nothing saved yet — add it to the "
                   f"knowledge base from the Results page if you want to keep it.")
        st.button("View results →", on_click=lambda: _go("② Results"), type="primary")


# --------------------------------------------------------------------------- Results
def _gate_strip(result) -> None:
    g = result.gates
    n = len(g) or len(result.config.tickers)
    g1 = sum(1 for v in g.values() if v["size"].passed)
    g2 = sum(1 for v in g.values() if v["fund"].overall == "pass")
    g3 = sum(1 for v in g.values() if v.get("exposure") and v["exposure"].status == "pass")
    g4 = sum(1 for o in result.outputs.values() if o.trend.passed)
    cols = st.columns(4)
    cols[0].metric("Gate 1 · Size", f"{g1}/{n}", help="Market cap ≥ size floor")
    cols[1].metric("Gate 2 · Fundamentals", f"{g2}/{n}", help="Margin, leverage, beat, valuation")
    cols[2].metric("Gate 3 · AI exposure", f"{g3}/{n}", help="Gemini-confirmed & approved (run per stock below)")
    cols[3].metric("Gate 4 · Idiosyncratic", f"{g4}/{len(result.outputs)}", help="The regression (α+ε up)")


def _render_gate_detail(result, ticker: str) -> None:
    gb = result.gates.get(ticker)
    if not gb:
        return
    size, fund = gb["size"], gb["fund"]
    st.markdown(f"**Gate 1 · Size** — {_bool_glyph(size.passed)} {size.note}")
    st.markdown(f"**Gate 2 · Fundamentals** — {_GLYPH.get(fund.overall, '?')} overall (`{fund.overall}`)")
    for name, mv in fund.metrics.items():
        st.caption(f"{_GLYPH.get(mv.status, '?')} {name.replace('_', ' ')}: {mv.note}")


def _render_exposure(result, run_id: str, ticker: str, o) -> None:
    st.markdown("**Gate 3 · AI exposure** — propose-and-approve (Gemini reads real news; you confirm)")
    if not gemini_available():
        st.caption("Gemini CLI not found — agent disabled.")
        return
    pk, dk, tk = f"prop::{run_id}::{ticker}", f"dec::{run_id}::{ticker}", f"typ::{run_id}::{ticker}"
    if st.button(f"🔎 Run AI-exposure agent for {ticker}", key="run_" + pk):
        with st.spinner(f"Researching {ticker} from recent news via Gemini…"):
            st.session_state[pk] = confirm_exposure(ticker)
            st.session_state[tk] = st.session_state[pk].type
            st.session_state.pop(dk, None)          # a fresh proposal resets the decision

    prop = st.session_state.get(pk)
    if prop is None:
        st.caption("Not run yet.")
        return
    if prop.error:
        st.error(f"Agent error: {prop.error}")
        return

    st.caption(f"Proposed from {prop.n_sources} real news items · {prop.summary}")
    if prop.comment:
        st.markdown(f"**🧠 Agent's view:** {prop.comment}")
    if prop.bullets:
        st.warning("⚠ Proposed — verify each source link before approving.")
        for b in prop.bullets:
            st.markdown(f"- **[{b['status']}]** {b['claim']}  \n  [🔗 source]({b['source']})")
    else:
        st.info("No sourced AI/data-center exposure found in recent news "
                "(the agent under-claimed rather than guess).")

    opts = TYPES + ([] if prop.type in TYPES else [prop.type])
    cur = st.session_state.get(tk, prop.type)
    sel = st.selectbox("Type (drives the relative-strength benchmark)", opts,
                       index=opts.index(cur) if cur in opts else 0, key="type_" + pk)
    st.session_state[tk] = sel
    prop.type = sel

    c1, c2, _ = st.columns([1, 1, 3])
    if c1.button("✅ Approve", key="ap_" + pk):
        st.session_state[dk] = "approved"
    if c2.button("❌ Reject", key="rj_" + pk):
        st.session_state[dk] = "rejected"

    decision = st.session_state.get(dk)
    verdict = exposure_verdict(prop, decision)
    result.gates.setdefault(ticker, {})["exposure"] = verdict
    st.markdown(f"**Gate 3 verdict:** {_GLYPH.get(verdict.status, '?')} `{verdict.status}` — {verdict.note}")

    if decision == "approved":
        bench = benchmark_for_type(sel, result.config.benchmark_map)
        if not bench:
            st.caption(f"No benchmark mapped for type '{sel}'.")
            return
        rk = f"rel::{run_id}::{ticker}::{bench}"
        if rk not in st.session_state:
            with st.spinner(f"Computing relative strength vs {bench}…"):
                st.session_state[rk] = relative_strength(o.reg.stock_returns, bench)
        rel = st.session_state[rk]
        if rel is not None and len(rel):
            st.plotly_chart(fig_relative_strength(rel, ticker, bench), use_container_width=True)
        else:
            st.caption(f"Relative strength vs {bench} unavailable (benchmark data not returned).")


def _explain_button(o, run_id: str) -> None:
    key = f"explain::{run_id}::{o.ticker}"
    disabled = not gemini_available()
    if st.button(f"🧠 How to read {o.ticker} (ask Gemini)", key="btn_" + key, disabled=disabled):
        with st.spinner("Asking Gemini to explain this result…"):
            try:
                st.session_state[key] = explain_stock(o)
            except GeminiAuthError as e:
                st.session_state[key] = f"⚠️ {e}"
            except GeminiError as e:
                st.session_state[key] = f"⚠️ Gemini call failed: {e}"
    if st.session_state.get(key):
        st.info(st.session_state[key])


def _save_control(result, run_id: str) -> None:
    """Opt-in 'Add to Knowledge Base' (no auto-save). Shows saved state once persisted."""
    if st.session_state.get("saved"):
        st.success("✓ Saved to the knowledge base — find it under ③ History.")
        return
    c1, c2 = st.columns([2, 1])
    name = c1.text_input("Run name", value=st.session_state.get("run_name", ""),
                         key=f"savename::{run_id}", label_visibility="collapsed",
                         placeholder="Name this run (optional)")
    if c2.button("💾 Add to Knowledge Base", type="primary", key=f"save::{run_id}"):
        with st.spinner("Saving run + charts to the knowledge base…"):
            store.save_run(result, run_id, name=name, make_charts=True)
        st.session_state.saved = True
        st.session_state.run_name = name
        st.rerun()


def page_results() -> None:
    result = st.session_state.get("result")
    if result is None:
        st.info("No run yet — go to **① New Run** and run a screen.")
        return
    run_id = st.session_state.get("run_id", "")
    _save_control(result, run_id)
    render_dashboard(result, run_id)


def render_dashboard(result, run_id: str) -> None:
    cfg = result.config
    _hero("Results", f"as-of {cfg.as_of_date}  ·  factor set <b>{cfg.factor_set}</b>  ·  "
                     f"horizon {cfg.time_horizon_days}d  ·  {len(result.outputs)} scored")

    _eyebrow("Scorecard · all gates, every ticker")
    _gate_strip(result)
    st.write("")
    if result.gates or result.outputs:
        st.dataframe(style_scorecard(build_scorecard(result)), use_container_width=True,
                     hide_index=True)
    st.caption("Ranked by **risk-adjusted alpha (info ratio)**, not raw return. "
               "**α sig?** ✓ = the own-merit drift is statistically real · ⚠ = positive but noise-driven · "
               "✗ = none. Verdict colour: green = pass / Track 1 · amber = flag / Track 2 · red = fail / "
               "Reject · slate = unverified. `⚠` on α+ε = tracking-noise risk (read with R²).")
    if result.skipped:
        st.warning("Skipped (insufficient/aligned data — reported, never faked): "
                   + "; ".join(f"{t} ({why})" for t, why in result.skipped))
    if set(cfg.factor_logical) & {"oil", "gas"}:
        st.caption(f"ℹ️ {OIL_FACTOR_CAVEAT}")
    if {"oil", "brent"} <= set(cfg.factor_logical):
        st.warning(f"⚠ {BRENT_COLLINEARITY_CAVEAT}")

    if len(result.outputs) > 1:
        _eyebrow("Combined idiosyncratic (α+ε) · ranking")
        st.plotly_chart(fig_combined_idio(result.outputs), use_container_width=True)

    _eyebrow("Per-stock detail")
    order = sorted(result.outputs, key=lambda t: result.outputs[t].trend.rank_key, reverse=True)
    for i, t in enumerate(order):
        o = result.outputs[t]
        tr = o.trend
        with st.expander(f"{t} — {tr.track_tag}", expanded=(i == 0)):
            asig = "apx-pass" if tr.alpha_significant else ("apx-flag" if tr.alpha_annualized > 0 else "apx-fail")
            alabel = ("real alpha ✓" if tr.alpha_significant
                      else ("alpha not significant ⚠" if tr.alpha_annualized > 0 else "no positive alpha ✗"))
            st.markdown(_track_pill(tr.track_tag) + "&nbsp;&nbsp;" + _pill(alabel, asig),
                        unsafe_allow_html=True)
            st.caption(tr.verdict_line)
            st.caption(f"**Alpha read:** {tr.alpha_verdict}")
            m = st.columns(5)
            m[0].metric("α (annualized)", f"{tr.alpha_annualized:+.0%}",
                        help="Persistent daily drift the factors don't explain, annualized.")
            m[1].metric("α t-stat", f"{tr.alpha_tstat:+.2f}",
                        help="|t| ≳ 2 ⇒ alpha is statistically real (not luck).")
            m[2].metric("Info ratio", f"{tr.information_ratio:.2f}",
                        help="Annualized α ÷ idiosyncratic volatility — quality of the alpha.")
            m[3].metric("Idiosyncratic α+ε", f"{tr.idio_endpoint:+.0%}",
                        delta="tracking-noise risk" if tr.tracking_noise else None, delta_color="off")
            m[4].metric("R²", f"{o.reg.r2:.2f}")
            if tr.tracking_noise:
                st.warning(f"⚠ {tr.tracking_noise_note}")
            cob = combined_oil_beta(o.reg)
            if cob is not None:
                st.caption(f"**Combined oil β (WTI+Brent): {cob:+.2f}** — use this, not the two "
                           f"individual oil betas (they're collinear and unstable).")

            tabs = st.tabs(["🎯 Alpha", "📈 Trend", "📐 Regression fit", "🔗 Decoupling",
                            "💧 Attribution", "🏭 Gates & AI exposure"])
            with tabs[0]:
                st.plotly_chart(fig_alpha_decomposition(o), use_container_width=True)
                st.caption("Dashed line = the pure persistent drift (α only). When the solid α+ε path "
                           "hugs it, the outperformance is steady and real; when α+ε wanders far from a "
                           "flat dashed line, the return is noise / one-off moves — visible return, but "
                           "no *proven* alpha. This is the difference between this tool and just reading "
                           "the price.")
            with tabs[1]:
                st.plotly_chart(fig_raw_vs_idio_single(o), use_container_width=True)
                if set(cfg.factor_logical) & {"oil", "gas"}:
                    st.caption(f"ℹ️ {OIL_FACTOR_CAVEAT}")
            with tabs[2]:
                st.plotly_chart(fig_regression_fit(o), use_container_width=True)
                st.caption("Each point is one trading day. The tighter the cloud hugs the dashed y=x "
                           "line, the more of the stock's daily moves the factors explain (higher R²).")
            with tabs[3]:
                st.plotly_chart(fig_rolling_single(o), use_container_width=True)
                st.caption("Dotted line = the static full-year value (the 'actual' beta/correlation). "
                           "Rolling beta = cov(stock, oil) / var(oil), so it can fall simply because "
                           "**oil's own volatility rose** (a bigger denominator) — not because the stock "
                           "decoupled. That shared denominator is why unrelated names can drop in sync. "
                           "These are *univariate* betas; the scorecard's β columns are the model's "
                           "(multivariate, partial) betas.")
            with tabs[4]:
                st.plotly_chart(fig_attribution_single(o), use_container_width=True)
                st.caption("Additive breakdown — the slices sum linearly to the total. (Headline "
                           "returns use compounding; this panel is the one linear breakdown.)")
            with tabs[5]:
                _render_gate_detail(result, t)
                st.divider()
                _render_exposure(result, run_id, t, o)

            _explain_button(o, run_id)

    if os.path.isdir(result.output_dir or ""):
        st.caption(f"Interactive HTML charts also saved to `{result.output_dir}`")


# --------------------------------------------------------------------------- History
def page_history() -> None:
    _hero("History / knowledge base", "Only runs you add are kept — each re-opens the full report.")
    runs = store.list_runs()
    if not runs:
        st.info("No saved runs yet. Run a screen, then click **Add to Knowledge Base** on the "
                "Results page to keep it here.")
        return
    _eyebrow(f"{len(runs)} saved run(s)")
    rows = [{
        "name": m.get("name", m.get("run_id")),
        "as-of": m.get("as_of_date"), "factor set": m.get("factor_set"),
        "horizon": m.get("time_horizon_days"), "tickers": " ".join(m.get("tickers", [])),
        "summary": ", ".join(f"{k}:{v}" for k, v in (m.get("summary") or {}).items()),
        "saved": m.get("timestamp"), "run_id": m.get("run_id"),
    } for m in runs]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    labels = {f"{m.get('name', m['run_id'])}  ·  {m.get('as_of_date')}  ({m['run_id'][:8]}…)": m["run_id"]
              for m in runs}
    chosen_label = st.selectbox("Open a saved run", list(labels))
    if not chosen_label:
        return
    chosen = labels[chosen_label]
    full = store.load_full_run(chosen)
    if full is not None:
        # Re-render the exact dashboard from the saved full result.
        render_dashboard(full, chosen)
    else:
        # Fallback: older run without a pickle — show the scorecard snapshot.
        meta, df = store.load_run(chosen)
        st.info("This run predates full-report saving — showing the scorecard snapshot only.")
        st.write(f"**{meta.get('name', chosen)}** — {' '.join(meta.get('tickers', []))} · "
                 f"{meta.get('factor_set')} · {meta.get('time_horizon_days')}d · saved {meta.get('timestamp')}")
        if df is not None:
            st.dataframe(style_scorecard(df), use_container_width=True, hide_index=True)
        notes = meta.get("data_notes") or {}
        if notes.get("oil_factor_caveat"):
            st.caption(f"ℹ️ {notes['oil_factor_caveat']}")


# --------------------------------------------------------------------------- route
if page == PAGES[0]:
    page_new_run()
elif page == PAGES[1]:
    page_results()
else:
    page_history()
