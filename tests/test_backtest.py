"""Offline contract tests for the walk-forward backtester (src/backtest/engine.py).

Synthetic price frame (no network). Locks the payload shape, the equity/date alignment, and the
insufficient-history guard. Numeric strategy behaviour is validated live; here we pin the mechanics.
"""
import numpy as np
import pandas as pd
import pytest

from src.backtest.engine import run_backtest


def _frame(n_days=520, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_days)
    market = rng.normal(0.0004, 0.01, n_days)
    # three stocks loading on the market plus their own noise; AAA gets a positive idiosyncratic drift
    data = {"market": market}
    for name, alpha, beta in [("AAA", 0.0010, 1.1), ("BBB", 0.0000, 0.9), ("CCC", -0.0005, 1.0)]:
        data[name] = alpha + beta * market + rng.normal(0, 0.012, n_days)
    return pd.DataFrame(data, index=dates)


def test_payload_shape_and_alignment():
    frame = _frame()
    res = run_backtest(frame, ["AAA", "BBB", "CCC"], ["market"],
                       risk_window=252, signal_window=63, rebalance=21, cost_bps=10.0, test_days=200)
    for key in ("dates", "neutral", "longOnly", "stats", "params"):
        assert key in res
    assert len(res["dates"]) == len(res["neutral"]["equity"]) == res["stats"]["nDays"]
    assert len(res["longOnly"]["equity"]) == len(res["dates"])
    # equity is a growth path starting within one day's move of 1.0
    assert res["neutral"]["equity"][0] == pytest.approx(1.0, abs=0.05)
    assert res["stats"]["nRebalances"] >= 1
    assert res["params"]["riskWindow"] == 252 and res["params"]["signalWindow"] == 63


def test_insufficient_history_raises():
    frame = _frame(n_days=280)          # only ~28 usable days after a 252 warm-up
    with pytest.raises(ValueError):
        run_backtest(frame, ["AAA", "BBB"], ["market"],
                     risk_window=252, signal_window=63, rebalance=21, cost_bps=10.0, test_days=760)


def test_no_qualifying_names_gives_flat_book():
    # only a down-drift name -> never a Core-long -> book sits in cash -> flat equity, no crash
    frame = _frame()
    res = run_backtest(frame, ["CCC"], ["market"],
                       risk_window=252, signal_window=63, rebalance=21, cost_bps=10.0, test_days=200)
    assert res["stats"]["avgLongs"] == 0.0
    assert res["neutral"]["equity"][-1] == pytest.approx(1.0, abs=1e-9)
