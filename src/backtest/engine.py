"""Walk-forward backtester for the market-neutral factor-model book.

Strategy replayed each rebalance (identical to the live opportunity engine, so we test the signal we
actually ship): fit each stock's factor regression on the TRAILING risk window → keep the names that
are Core-long quality (real +idio alpha, clears the IR bar) AND whose idiosyncratic gap is *opening*
over the shorter SIGNAL window → equal-weight them long → short the factor proxies sized to zero the
book's net factor beta (the executable market-neutral hedge). Held to the next rebalance, net of a
turnover cost. Also tracks an unhedged long-only book for comparison.

No look-ahead: at rebalance index i the betas are fit on returns[i-risk_window : i] (strictly before
day i), and those weights earn day i's realized return onward. Costs are charged on turnover at each
rebalance. Neutrality is verified ex-post (realized market beta of the book returns ≈ 0).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..gates.trend import IDIO_MAGNITUDE_FLAG, R2_HIGH
from ..opportunity.engine import NON_HEDGE_FACTORS, OPP_DEADBAND, OPP_MIN_IR

TRADING_DAYS = 252


def _nw_maxlags(n: int) -> int:
    return max(1, int(np.floor(4.0 * (n / 100.0) ** (2.0 / 9.0))))


def _fast_fit(y: np.ndarray, Xf: np.ndarray):
    """Hand-rolled OLS with Newey-West (HAC) intercept t-stat — numerically identical to the
    statsmodels path (validated) but ~10-30× faster, so a big-universe walk-forward finishes inside
    the request timeout. Returns (alpha, betas, resid, r2, alpha_tstat)."""
    n = len(y)
    X = np.column_stack([np.ones(n), Xf])
    XtX_inv = np.linalg.inv(X.T @ X)
    b = XtX_inv @ (X.T @ y)
    e = y - X @ b
    yc = y - y.mean()
    ss_tot = float(yc @ yc)
    r2 = 1.0 - float(e @ e) / ss_tot if ss_tot > 0 else 0.0
    k = X.shape[1]
    L = _nw_maxlags(n)
    u = X * e[:, None]                                  # score x_t*e_t
    S = u.T @ u
    for lag in range(1, L + 1):
        w = 1.0 - lag / (L + 1.0)                       # Bartlett weight
        G = u[lag:].T @ u[:-lag]
        S += w * (G + G.T)
    S *= n / (n - k)                                    # small-sample correction (use_correction=True)
    var_alpha = float((XtX_inv @ S @ XtX_inv)[0, 0])
    se = var_alpha ** 0.5
    t = float(b[0] / se) if se > 0 else 0.0
    return float(b[0]), b[1:], e, float(r2), t


def _fast_fit_many(Y: np.ndarray, Xf: np.ndarray):
    """Vectorised OLS + HAC intercept t-stat for MANY stocks that share the same factor matrix Xf —
    one matrix solve for the whole universe (they differ only in y). Returns alpha (m,), betas (k,m),
    resid E (n,m), r2 (m,), alpha_tstat (m,). Numerically identical to _fast_fit per column."""
    n, m = Y.shape
    X = np.column_stack([np.ones(n), Xf])
    XtX_inv = np.linalg.inv(X.T @ X)
    B = XtX_inv @ (X.T @ Y)                              # (k+1, m)
    E = Y - X @ B                                        # (n, m)
    alpha = B[0]
    ss_res = (E * E).sum(0)
    Yc = Y - Y.mean(0, keepdims=True)
    ss_tot = (Yc * Yc).sum(0)
    r2 = np.where(ss_tot > 0, 1.0 - ss_res / ss_tot, 0.0)
    k = X.shape[1]
    L = _nw_maxlags(n)
    # var(alpha_j) = c' S_j c, with c = XtX_inv[:,0]. Since c'·(x_t e_{j,t}) = (X_t·c) e_{j,t} = h_t e_{j,t},
    # everything reduces to the scalar series G = h ⊙ E — fully vectorised over stocks.
    c = XtX_inv[:, 0]
    h = X @ c                                            # (n,)
    G = h[:, None] * E                                   # (n, m)
    var = (G * G).sum(0)
    for lag in range(1, L + 1):
        w = 1.0 - lag / (L + 1.0)
        var += w * 2.0 * (G[lag:] * G[:-lag]).sum(0)
    var *= n / (n - k)
    se = np.sqrt(np.maximum(var, 0.0))
    tstat = np.where(se > 0, alpha / se, 0.0)
    return alpha, B[1:], E, r2, tstat


def load_returns(stocks: list[str], factor_map: dict[str, str], min_days: int):
    """Download aligned daily returns for stocks + factor proxies. Factor columns are renamed to their
    LOGICAL name (market, oil, fx, …). Returns (frame, present_stocks, present_factors, missing)."""
    import yfinance as yf

    proxies = list(dict.fromkeys(factor_map.values()))
    tickers = list(dict.fromkeys(list(stocks) + proxies))
    period_days = max(int(min_days) + 400, 900)
    data = yf.download(tickers, period=f"{period_days}d", auto_adjust=True, progress=False)
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    rets = close.dropna(how="all").pct_change()

    frame = pd.DataFrame(index=rets.index)
    missing: list[str] = []
    present_stocks: list[str] = []
    for s in stocks:
        if s in rets.columns:
            frame[s] = rets[s]; present_stocks.append(s)
        else:
            missing.append(s)
    present_factors: list[str] = []
    for logical, proxy in factor_map.items():
        if proxy in rets.columns:
            frame[logical] = rets[proxy]; present_factors.append(logical)
        else:
            missing.append(f"{logical} ({proxy})")
    frame = frame.dropna()
    present_stocks = [s for s in present_stocks if s in frame.columns]
    return frame, present_stocks, present_factors, missing


def _book_weights(train: pd.DataFrame, stocks: list[str], factors: list[str], signal_window: int, *,
                  use_signal_gate: bool, min_longs: int, max_weight: float,
                  min_tstat: float = 2.0, min_ir: float = OPP_MIN_IR, max_longs: int = 0):
    """Weights at one rebalance. Returns (stock_weights, hedge_weights). Sits in cash (empty) unless at
    least `min_longs` names qualify (diversification). `use_signal_gate` toggles the recent-'improving'
    momentum filter. Single-name weight capped at `max_weight`. Hedge betas come from a clean refit on
    the non-collinear macro factors only."""
    hedge_factors = [f for f in factors if f not in NON_HEDGE_FACTORS]   # stable, non-collinear hedge basis
    Y = train[stocks].to_numpy(dtype=float)               # (n, m) — all stocks share the factor matrix
    Xf = train[factors].to_numpy(dtype=float)
    try:
        alpha, _B, E, r2, tstat = _fast_fit_many(Y, Xf)   # ONE solve for the whole universe (HAC t-stat)
    except Exception:
        return {}, {}
    Bh = None
    if hedge_factors:
        try:
            _, Bh, _, _, _ = _fast_fit_many(Y, train[hedge_factors].to_numpy(dtype=float))
        except Exception:
            Bh = None
    n, sw2 = Y.shape[0], (signal_window if signal_window and signal_window > 0 else None)
    qualified: list[tuple[str, float, dict]] = []
    for j, s in enumerate(stocks):
        if not (alpha[j] > 0 and tstat[j] >= min_tstat):  # tunable conviction bar (was t≥2)
            continue
        e = E[:, j]
        idio = alpha[j] + e
        idio_end = float(np.prod(1.0 + idio) - 1.0)
        if idio_end <= OPP_DEADBAND:                      # own-story must be up (Core-long)
            continue
        if abs(idio_end) >= IDIO_MAGNITUDE_FLAG and r2[j] >= R2_HIGH:   # tracking-noise flag → skip
            continue
        rv = float(np.std(e, ddof=1) * np.sqrt(TRADING_DAYS))
        ir = (alpha[j] * TRADING_DAYS) / rv if rv > 0 else float("nan")
        if not (ir == ir and ir >= min_ir):
            continue
        if use_signal_gate:
            recent = idio[-sw2:] if sw2 else idio
            if len(recent) == 0 or float(np.prod(1.0 + recent) - 1.0) <= OPP_DEADBAND:
                continue                                  # only enter when the recent gap is IMPROVING
        hbetas = {hedge_factors[i]: float(Bh[i, j]) for i in range(len(hedge_factors))} if Bh is not None else {}
        qualified.append((s, ir, hbetas))
    if len(qualified) < max(1, min_longs):             # diversification floor → else cash
        return {}, {}
    if max_longs and len(qualified) > max_longs:       # keep only the top-N by information ratio
        qualified = sorted(qualified, key=lambda q: q[1], reverse=True)[:max_longs]
    w = min(1.0 / len(qualified), max_weight)          # equal weight, single-name capped
    stock_w = {s: w for s, _, _ in qualified}
    net: dict[str, float] = {}
    for _, _, hb in qualified:
        for f, b in hb.items():
            net[f] = net.get(f, 0.0) + w * float(b)
    hedge_w = {f: -net[f] for f in net if f in hedge_factors}   # short proxies to zero net macro beta
    return stock_w, hedge_w


def _turnover(new: dict, old: dict) -> float:
    return sum(abs(new.get(c, 0.0) - old.get(c, 0.0)) for c in set(new) | set(old))


def _series_stats(dates, rets) -> dict:
    s = pd.Series(rets, index=pd.to_datetime(dates))
    eq = (1.0 + s).cumprod()
    end = float(eq.iloc[-1]) if len(eq) else 1.0
    yrs = len(s) / TRADING_DAYS if len(s) else 0.0
    vol = float(s.std(ddof=1) * np.sqrt(TRADING_DAYS)) if len(s) > 1 else 0.0
    dd = float((eq / eq.cummax() - 1.0).min()) if len(eq) else 0.0
    return {
        "equity": [float(v) for v in eq],
        "totalReturn": end - 1.0,
        "cagr": (end ** (1.0 / yrs) - 1.0) if yrs > 0 and end > 0 else float("nan"),
        "annVol": vol,
        "sharpe": float(s.mean() * TRADING_DAYS / vol) if vol > 0 else float("nan"),
        "maxDrawdown": dd,
    }


def run_backtest(frame: pd.DataFrame, stocks: list[str], factors: list[str], *, risk_window: int,
                 signal_window: int, rebalance: int, cost_bps: float, test_days: int,
                 min_longs: int = 3, max_weight: float = 0.35, use_signal_gate: bool = True,
                 borrow_bps: float = 50.0, min_tstat: float = 2.0, min_ir: float = OPP_MIN_IR,
                 max_longs: int = 0) -> dict:
    """Walk forward over the last `test_days` of `frame`, rebalancing every `rebalance` days.

    Improvements over v1: diversification floor (`min_longs`) + single-name cap (`max_weight`),
    optional entry-gate (`use_signal_gate`), an annual short-borrow drag (`borrow_bps`), and equal-weight
    buy-hold benchmarks (basket + market) plus tail stats. All still no-look-ahead.
    """
    rate = float(cost_bps) / 10000.0
    borrow_daily = (float(borrow_bps) / 10000.0) / TRADING_DAYS
    dates = frame.index
    n = len(dates)
    start = max(int(risk_window), n - int(test_days))
    if n - start < rebalance * 2 + 1:
        raise ValueError("Not enough price history for this risk window / test window. "
                         "Shorten the risk window or the test length, or add history.")

    w_all: dict[str, float] = {}
    w_long: dict[str, float] = {}
    out_dates, r_neutral, r_long = [], [], []
    turnovers, nlongs = [], []
    period_neutral: list[float] = []          # compounded return within each rebalance period (hit rate)
    cur_period = 1.0

    for i in range(start, n):
        rebal = (i - start) % rebalance == 0
        cost_all = cost_long = 0.0
        if rebal:
            if i > start:
                period_neutral.append(cur_period - 1.0)
            cur_period = 1.0
            train = frame.iloc[i - risk_window:i]
            sw, hw = _book_weights(train, stocks, factors, signal_window,
                                   use_signal_gate=use_signal_gate, min_longs=min_longs,
                                   max_weight=max_weight, min_tstat=min_tstat, min_ir=min_ir,
                                   max_longs=max_longs)
            new_all, new_long = {**sw, **hw}, dict(sw)
            cost_all = _turnover(new_all, w_all) * rate
            cost_long = _turnover(new_long, w_long) * rate
            turnovers.append(_turnover(new_all, w_all))
            nlongs.append(len(sw))
            w_all, w_long = new_all, new_long
        row = frame.iloc[i]
        short_notional = sum(-wt for wt in w_all.values() if wt < 0)   # shorts pay borrow
        rn = (sum(w_all.get(c, 0.0) * float(row[c]) for c in w_all)
              - cost_all - short_notional * borrow_daily)
        rl = sum(w_long.get(c, 0.0) * float(row[c]) for c in w_long) - cost_long
        out_dates.append(dates[i]); r_neutral.append(rn); r_long.append(rl)
        cur_period *= (1.0 + rn)
    period_neutral.append(cur_period - 1.0)

    # benchmarks over the SAME dates: equal-weight buy-hold of the basket, and the market factor.
    sub = frame.loc[pd.to_datetime(out_dates)]
    bench_basket = sub[stocks].mean(axis=1).tolist()
    market_bh = sub["market"].tolist() if "market" in frame.columns else None

    neutral = _series_stats(out_dates, r_neutral)
    longonly = _series_stats(out_dates, r_long)
    basket = _series_stats(out_dates, bench_basket)
    market = _series_stats(out_dates, market_bh) if market_bh is not None else None

    # ex-post neutrality: realized beta of the book to the market factor (should be ≈ 0).
    realized_beta = None
    if "market" in frame.columns:
        mkt = sub["market"].to_numpy()
        bk = np.asarray(r_neutral)
        ok = np.isfinite(mkt) & np.isfinite(bk)
        if ok.sum() > 2:
            v = float(np.var(mkt[ok]))
            if v > 0:
                realized_beta = float(np.cov(bk[ok], mkt[ok])[0, 1] / v)

    wins = [p for p in period_neutral if p == p]
    hit_rate = float(np.mean([1.0 if p > 0 else 0.0 for p in wins])) if wins else float("nan")
    arr = np.asarray(r_neutral)
    worst = float(arr.min()) if len(arr) else float("nan")
    best = float(arr.max()) if len(arr) else float("nan")
    pos_days = float((arr > 0).mean()) if len(arr) else float("nan")
    invested = float(np.mean([1.0 if k > 0 else 0.0 for k in nlongs])) if nlongs else 0.0

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in out_dates],
        "neutral": neutral,
        "longOnly": longonly,
        "basket": basket,                     # equal-weight buy-hold benchmark
        "market": market,                     # market factor buy-hold
        "stats": {
            "nDays": len(out_dates),
            "nRebalances": len(turnovers),
            "avgLongs": float(np.mean(nlongs)) if nlongs else 0.0,
            "avgTurnover": float(np.mean(turnovers)) if turnovers else 0.0,
            "pctInvested": invested,          # fraction of rebalances actually holding (vs cash)
            "hitRate": hit_rate,
            "posDays": pos_days,
            "worstDay": worst, "bestDay": best,
            "realizedMarketBeta": realized_beta,
            "costBps": float(cost_bps), "borrowBps": float(borrow_bps),
        },
        "params": {"riskWindow": int(risk_window), "signalWindow": int(signal_window),
                   "rebalance": int(rebalance), "testDays": int(test_days),
                   "minLongs": int(min_longs), "maxWeight": float(max_weight),
                   "useSignalGate": bool(use_signal_gate), "minTstat": float(min_tstat),
                   "minIr": float(min_ir)},
    }
