"""Entrypoint / orchestrator.

Per docs/PLATFORM.md, the real work lives in an importable `run_screen(config)` so the future UI
(Step 5) calls the exact same code path as the CLI. `main()` is only a thin argparse wrapper.

README quick-start:
    python -m src.main --tickers VST CEG NRG VRT ETN --factor-set 4factor --horizon 252
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field

from .config import FACTOR_SETS, Config, load_config
from .data.fundamentals import get_backend
from .data.market_cap import get_market_cap
from .data.prices import build_return_panel
from .gates.fundamentals import FundVerdict, check_fundamentals
from .gates.size import SizeVerdict, check_size
from .gates.trend import TrendVerdict, check_trend
from .regression.attribution import attribution
from .regression.engine import RegressionResult, run_regression
from .regression.rolling import (factor_correlation_table, rolling_correlation,
                                 rolling_partial_beta, static_correlation)
from .regression.variance import (DriverStability, VarianceDecomposition,
                                  decompose_variance, stability)
from .data.sector import sector_map_for
from .viz import charts


@dataclass
class StockOutput:
    ticker: str
    reg: RegressionResult
    trend: TrendVerdict
    attr: dict
    headline_corr: dict            # {commodity: {'corr','beta'}} over the headline (last-year) window
    roll_corr: "object"            # DataFrame sliced to the horizon window
    roll_beta: "object"
    raw_6m: float | None
    raw_12m: float | None
    variance: VarianceDecomposition | None = None   # Performance-Drivers variance shares (v2 panel)
    factor_table: dict = field(default_factory=dict)  # {factor: {'corr6m','corr1y'}} — JPM factor table
    sector_etf: str | None = None                    # this stock's GICS sector ETF (drivers mode)
    driver_stability: DriverStability | None = None  # 1Y-vs-6M share stability of the variance panel


@dataclass
class ScreenResult:
    config: Config
    outputs: dict                  # ticker -> StockOutput (Gate-4 pass/fail + regression detail)
    skipped: list                  # [(ticker, reason)]
    output_dir: str
    gates: dict = field(default_factory=dict)   # ticker -> {size, fund_raw, fund} (Gates 1-2, every ticker)
    chart_paths: list = field(default_factory=list)
    table_path: str | None = None
    dropped_factors: list = field(default_factory=list)   # shared factors that failed to download


def _default_output_dir(config: Config) -> str:
    return os.path.join("runs", f"{config.as_of_date.isoformat()}_{config.factor_set}")


def _compute_gates(config: Config) -> dict:
    """Gates 1 (size) and 2 (fundamentals) for EVERY input ticker — scorecard, not funnel
    (CLAUDE.md rule 6). Per-ticker errors degrade to 'unverified', never fabricated."""
    backend = get_backend(config.fundamentals_source)
    gates: dict = {}
    for t in config.tickers:
        try:
            size = check_size(get_market_cap(t), config.size_floor_usd)
        except Exception as e:  # network / data hiccup -> unverified, not a guess
            size = SizeVerdict(None, None, f"unavailable ({type(e).__name__})")
        try:
            raw = backend.get_fundamentals(t)
            fund = check_fundamentals(raw, config.leverage_flag_net_debt_ebitda)
        except Exception as e:
            raw = {"values": {}, "unverified": set()}
            fund = FundVerdict("unverified", {})
        gates[t] = {"size": size, "fund_raw": raw, "fund": fund}
    return gates


def run_screen(config: Config, make_charts: bool = True) -> ScreenResult:
    """Run the Step-1 pipeline (Gate 4 regression + diagnostics + charts) on every ticker.

    Scorecard, not funnel: every ticker with usable data is computed; those without are reported in
    `skipped`, never silently dropped or faked (CLAUDE.md rules 2 & 6).
    """
    horizon = config.time_horizon_days
    commodities = config.commodity_logical
    # Equipment names (boss: fundamentals-only, no regression) are kept out of the price panel entirely.
    equipment = {t.upper() for t in config.equipment_tickers}
    reg_tickers = [t for t in config.tickers if t.upper() not in equipment]
    # Performance-Drivers mode regresses each stock on its OWN GICS sector ETF (per-stock factor).
    sector_by_ticker = sector_map_for(reg_tickers) if config.use_sector else {}
    panel = build_return_panel(reg_tickers, config.factor_map, horizon, config.as_of_date,
                               warmup=max(config.rolling_beta_days, config.rolling_corr_days),
                               sector_by_ticker=sector_by_ticker)

    outputs: dict[str, StockOutput] = {}
    for t in reg_tickers:
        frame = panel.stocks.get(t)
        if frame is None:
            continue
        window = frame.tail(horizon)
        stock_win = window[t]
        # Factor columns from the FRAME (not config.factor_logical) so a per-stock 'sector' column is
        # included and any download-dropped shared factor is naturally excluded.
        factor_cols = [c for c in window.columns if c != t]
        factor_win = window[factor_cols]
        reg = run_regression(stock_win, factor_win)

        # headline static correlation over the last-year window; rolling over the full frame, then
        # sliced to the displayed horizon so the decoupling view has no warm-up gap.
        head = frame.tail(config.corr_headline_days)
        headline_corr = static_correlation(head[t], head[commodities]) if commodities else {}
        roll_factors = [c for c in config.factor_logical if c in frame.columns]
        if commodities:
            rc = rolling_correlation(frame[t], frame[commodities], config.rolling_corr_days).loc[window.index]
            # MULTIVARIATE rolling beta on the full factor set, then show the commodity columns — same
            # beta definition as the scorecard, so rolling and table reconcile (no univariate mismatch).
            rb_full = rolling_partial_beta(frame[t], frame[roll_factors],
                                           config.rolling_beta_days).loc[window.index]
            rb = rb_full[commodities]
        else:
            import pandas as pd
            rc = rb = pd.DataFrame(index=window.index)

        # Performance-Drivers variance decomposition — same window & factors as the regression, so
        # idiosyncratic share (= 1 − R²) matches the model's R² exactly. Groups built from THIS stock's
        # factor columns (sector varies per stock).
        groups = config.groups_for_factors(factor_cols, config.custom_groups)
        variance = decompose_variance(stock_win, factor_win, groups)
        # Stability: recompute shares on the recent 6M window and compare to the 1Y — a share is only
        # trustworthy if it doesn't swing wildly between the two.
        short = window.tail(config.robustness_horizon_days)
        driver_stability = None
        if len(short) >= max(30, len(factor_cols) + 5):     # enough obs for a meaningful 6M refit
            variance_short = decompose_variance(short[t], short[factor_cols], groups)
            driver_stability = stability(variance, variance_short)
        # JPM-style 6M/1Y univariate correlation table, per active factor.
        factor_table = factor_correlation_table(frame, t, factor_cols,
                                                 short=config.robustness_horizon_days,
                                                 long=config.corr_headline_days)

        n = reg.n_obs
        outputs[t] = StockOutput(
            ticker=t,
            reg=reg,
            trend=check_trend(reg),
            attr=attribution(reg),
            headline_corr=headline_corr,
            roll_corr=rc,
            roll_beta=rb,
            raw_6m=reg.raw_return_compounded(min(126, n)) if n >= 20 else None,
            raw_12m=reg.raw_return_compounded(min(252, n)) if n >= 20 else None,
            variance=variance,
            factor_table=factor_table,
            sector_etf=sector_by_ticker.get(t.upper()),
            driver_stability=driver_stability,
        )

    gates = _compute_gates(config)
    output_dir = config.output_dir or _default_output_dir(config)
    result = ScreenResult(config=config, outputs=outputs, skipped=panel.skipped,
                          output_dir=output_dir, gates=gates,
                          dropped_factors=list(panel.dropped_factors))

    if make_charts and outputs:
        result.chart_paths += charts.chart_raw_vs_idiosyncratic(outputs, output_dir)
        result.chart_paths += charts.chart_variance_drivers(outputs, output_dir)
        result.chart_paths += charts.chart_rolling_decoupling(outputs, output_dir)
        result.chart_paths += charts.chart_attribution_waterfall(outputs, output_dir)
        result.table_path = charts.save_detail_table(outputs, output_dir)
    return result


def _ensure_utf8_stdout() -> None:
    """Windows consoles default to cp1252, which can't encode α/ε/² in the table. Prefer UTF-8."""
    import sys

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _print_report(result: ScreenResult) -> None:
    _ensure_utf8_stdout()
    cfg = result.config
    print(f"\nFactor-Alpha Screener — scorecard")
    print(f"as-of {cfg.as_of_date}  |  factor-set: {cfg.factor_set}  |  horizon: {cfg.time_horizon_days}d")
    print("=" * 78)
    if result.gates or result.outputs:
        print(charts.build_scorecard(result).to_string(index=False))
    if result.outputs:
        print("\nVerdicts (sorted by cumulative idiosyncratic α+ε):")
        order = sorted(result.outputs, key=lambda t: result.outputs[t].trend.rank_key, reverse=True)
        for t in order:
            o = result.outputs[t]
            print(f"  • {t}: {o.trend.track_tag}")
            print(f"       {o.trend.verdict_line}")
    else:
        print("No tickers produced regression output.")
    if result.skipped:
        print("\nSkipped (insufficient/aligned data — reported, not faked):")
        for t, why in result.skipped:
            print(f"  • {t}: {why}")
    if result.chart_paths:
        print(f"\nCharts + table written to: {result.output_dir}")
        for p in result.chart_paths + ([result.table_path] if result.table_path else []):
            print(f"  - {os.path.basename(p)}")


def main(argv=None) -> ScreenResult:
    ap = argparse.ArgumentParser(description="Factor-Alpha Screener — factor-model / performance-driver regression core")
    ap.add_argument("--tickers", nargs="+", required=True, help="one or more tickers, e.g. VST CEG NRG")
    ap.add_argument("--factor-set", dest="factor_set", choices=list(FACTOR_SETS), default=None)
    ap.add_argument("--horizon", type=int, default=None, help="beta+residual window in trading days")
    ap.add_argument("--as-of-date", dest="as_of_date", default=None, help="YYYY-MM-DD (default: today)")
    ap.add_argument("--output", dest="output_dir", default=None, help="output directory for charts")
    ap.add_argument("--config", dest="config_path", default="config.yaml")
    args = ap.parse_args(argv)

    config = load_config(
        args.config_path,
        tickers=args.tickers,
        factor_set=args.factor_set,
        horizon=args.horizon,
        as_of_date=args.as_of_date,
        output_dir=args.output_dir,
    )
    result = run_screen(config)
    _print_report(result)
    return result


if __name__ == "__main__":
    main()
