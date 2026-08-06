"""Configuration loading and factor-set resolution (docs/DATA.md §Config).

Reads config.yaml and applies per-run CLI overrides. `as_of_date` is a first-class field
(default: today) so a point-in-time backtest can be added later without a redesign (CLAUDE.md rule 5).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field

# Which logical factors are active in each mode. Proxy tickers come from config.yaml:factor_proxies.
# The idiosyncratic return is always (alpha + epsilon) of whichever model is chosen. No auto-switching.
FACTOR_SETS = {
    "4factor": ["market", "rates", "oil", "gas"],           # clean default (WTI only)
    "commodity": ["oil", "gas"],
    # boss's spec: market + WTI + Henry Hub. Brent was dropped (2026-07-23) — it's ~0.92 correlated
    # with WTI, so including both split the oil beta into meaningless individual coefficients (e.g. BE
    # −0.34 / +0.60) while adding ~no explanatory power. WTI alone gives one stable, readable oil beta.
    "boss": ["market", "oil", "gas"],
    # Performance-Drivers (v2) — the full JPM-style risk model. Shared factors here; 'sector' is
    # resolved PER STOCK at panel-build time (each stock regressed on its own GICS sector ETF), so it
    # is not listed as a shared logical factor. Style = 5 single-factor ETFs entered together (reported
    # as one Style group). Macro = credit (HYG) + base metals (DBB); rates & energy are their OWN groups.
    "drivers": ["market", "rates", "oil", "gas",
                "value", "growth", "momentum", "lowvol", "quality",
                "credit", "metals"],
}

# Modes that additionally regress each stock on its own (per-stock) GICS sector ETF.
SECTOR_MODES = {"drivers"}

# Driver GROUPS for the Performance-Drivers variance decomposition (v2). Each logical factor maps to a
# group; the variance engine (regression/variance.py) reports one variance share per group plus
# Idiosyncratic (= 1 − R²). Oil + gas collapse into a single ENERGY group, the 5 style ETFs into STYLE,
# and credit + metals into MACRO. Per the mandate we keep Energy AND Rates as their own groups (not
# folded into Macro like JPM) — the two macro drivers this universe cares about get read on their own.
FACTOR_GROUPS = {
    "market": "Market",
    "rates": "Rates",
    "oil": "Energy",
    "gas": "Energy",
    "brent": "Energy",
    "sector": "Sector",
    "value": "Style",
    "growth": "Style",
    "momentum": "Style",
    "lowvol": "Style",
    "quality": "Style",
    "credit": "Macro",
    "metals": "Macro",
}


@dataclass
class Config:
    tickers: list[str]
    factor_set: str = "4factor"
    time_horizon_days: int = 252         # RISK window: betas/alpha/hedge ratios (stable → executable neutral)
    signal_horizon_days: int = 63        # SIGNAL window: recent idiosyncratic trajectory (fast → fresh timing)
    corr_headline_days: int = 252
    rolling_corr_days: int = 63
    rolling_beta_days: int = 90
    robustness_horizon_days: int = 126
    return_frequency: str = "daily"
    factor_proxies: dict = field(default_factory=dict)
    size_floor_usd: float = 2_000_000_000
    leverage_flag_net_debt_ebitda: float = 6.0
    fundamentals_source: str = "public"
    benchmark_map: dict = field(default_factory=dict)
    exclude_tickers: list = field(default_factory=list)     # never covered (e.g. existing positions)
    equipment_tickers: list = field(default_factory=list)   # fundamentals-only; no regression (boss)
    as_of_date: _dt.date = field(default_factory=_dt.date.today)
    output_dir: str | None = None
    # --- custom / region-preset drivers (factor_set == 'custom') --------------------------------
    # When factor_set == 'custom' the active factors come from these instead of FACTOR_SETS: the user
    # (or a region preset) supplies logical-name -> proxy-ticker and, optionally, a group label per
    # driver. This is what makes the model region-agnostic (US SPY/TLT vs Indonesia ^JKSE/IDR=X …).
    custom_factors: dict = field(default_factory=dict)   # logical name -> proxy ticker
    custom_groups: dict = field(default_factory=dict)    # logical name -> driver group label

    @property
    def factor_logical(self) -> list[str]:
        """Active logical factor names for the chosen mode, e.g. ['market','rates','oil','gas']."""
        if self.factor_set == "custom":
            return list(self.custom_factors)
        return FACTOR_SETS[self.factor_set]

    @property
    def factor_map(self) -> dict[str, str]:
        """logical name -> proxy ticker, restricted to the active mode (e.g. {'oil':'CL=F', ...})."""
        if self.factor_set == "custom":
            return dict(self.custom_factors)
        return {name: self.factor_proxies[name] for name in self.factor_logical}

    @property
    def commodity_logical(self) -> list[str]:
        """The commodity factors present in both modes (used for correlation/decoupling diagnostics)."""
        return [c for c in ("oil", "gas") if c in self.factor_logical]

    @staticmethod
    def groups_for_factors(factors, custom_groups=None) -> dict[str, list[str]]:
        """Map a list of logical factor names -> {group: [factors]}. A custom driver's group (if the
        run supplied one via `custom_groups`) wins, else FACTOR_GROUPS, else the factor's own
        capitalised name. Order-preserving. Used per-stock because 'sector' varies by ticker, so the
        active factor list can differ across stocks."""
        custom_groups = custom_groups or {}
        groups: dict[str, list[str]] = {}
        for f in factors:
            g = custom_groups.get(f) or FACTOR_GROUPS.get(f, f.capitalize())
            groups.setdefault(g, []).append(f)
        return groups

    @property
    def driver_groups(self) -> dict[str, list[str]]:
        """Driver group -> the active SHARED logical factors composing it (excludes per-stock 'sector').
        Feeds the variance decomposition; callers pass a per-stock list when sector is present."""
        return self.groups_for_factors(self.factor_logical, self.custom_groups)

    @property
    def use_sector(self) -> bool:
        """True when this mode regresses each stock on its own GICS sector ETF (Performance Drivers)."""
        return self.factor_set in SECTOR_MODES


def load_config(path: str = "config.yaml", **overrides) -> Config:
    """Load config.yaml, apply CLI overrides, return a Config.

    Recognised overrides: tickers, factor_set, time_horizon_days (alias: horizon), as_of_date, output_dir.
    Overrides with value None are ignored (so unset CLI args don't clobber config defaults).
    """
    import yaml

    with open(path) as f:
        raw = yaml.safe_load(f) or {}

    if "horizon" in overrides and overrides["horizon"] is not None:
        overrides.setdefault("time_horizon_days", overrides["horizon"])
    overrides.pop("horizon", None)

    if overrides.get("factor_set") is None:
        overrides.pop("factor_set", None)
        overrides["factor_set"] = raw.get("factor_set_default", "4factor")

    as_of = overrides.get("as_of_date")
    if isinstance(as_of, str):
        overrides["as_of_date"] = _dt.date.fromisoformat(as_of)

    cfg = Config(
        tickers=[t.upper() for t in (overrides.get("tickers") or [])],
        factor_set=overrides.get("factor_set", raw.get("factor_set_default", "4factor")),
        time_horizon_days=overrides.get("time_horizon_days", raw.get("time_horizon_days", 252)),
        signal_horizon_days=(overrides.get("signal_horizon_days")
                             if overrides.get("signal_horizon_days") is not None
                             else raw.get("signal_horizon_days", 63)),
        corr_headline_days=raw.get("corr_headline_days", 252),
        rolling_corr_days=raw.get("rolling_corr_days", 63),
        rolling_beta_days=raw.get("rolling_beta_days", 90),
        robustness_horizon_days=raw.get("robustness_horizon_days", 126),
        return_frequency=raw.get("return_frequency", "daily"),
        factor_proxies=raw.get("factor_proxies", {}),
        size_floor_usd=(overrides.get("size_floor_usd")
                        if overrides.get("size_floor_usd") is not None
                        else raw.get("size_floor_usd", 2_000_000_000)),
        leverage_flag_net_debt_ebitda=raw.get("leverage_flag_net_debt_ebitda", 6.0),
        fundamentals_source=(overrides.get("fundamentals_source")
                             or raw.get("fundamentals_source", "public")),
        benchmark_map=raw.get("benchmark_map", {}),
        exclude_tickers=[t.upper() for t in raw.get("exclude_tickers", [])],
        equipment_tickers=[t.upper() for t in (overrides.get("equipment_tickers") or [])],
        custom_factors=dict(overrides.get("custom_factors") or {}),
        custom_groups=dict(overrides.get("custom_groups") or {}),
    )
    # Drop excluded names (e.g. GEV — existing position) before anything runs.
    if cfg.exclude_tickers:
        excl = set(cfg.exclude_tickers)
        cfg.tickers = [t for t in cfg.tickers if t not in excl]
    if overrides.get("as_of_date") is not None:
        cfg.as_of_date = overrides["as_of_date"]
    if overrides.get("output_dir") is not None:
        cfg.output_dir = overrides["output_dir"]
    if cfg.factor_set == "custom":
        if not cfg.custom_factors:
            raise ValueError("factor_set='custom' requires custom_factors {logical_name: ticker}")
    elif cfg.factor_set not in FACTOR_SETS:
        raise ValueError(f"factor_set must be 'custom' or one of {list(FACTOR_SETS)}, "
                         f"got {cfg.factor_set!r}")
    return cfg
