"""Walk-forward backtest of the market-neutral factor-model signal (price-only → feasible without
point-in-time fundamentals). Replays the SAME live signal code (run_regression + check_trend + the
opportunity bar) at each historical rebalance date, using ONLY trailing data (no look-ahead).
"""
from .engine import load_returns, run_backtest  # noqa: F401
