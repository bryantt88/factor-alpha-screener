"""Offline tests for the Phase-2 Performance-Drivers additions (drivers mode, sector, factor table).

No network: config resolution, group mapping (incl. per-stock sector), the 6M/1Y correlation table,
the sector resolver's override + fallback logic, and a full driver-set variance decomposition still
summing to 100%.
"""
import numpy as np
import pandas as pd

from src import data as _data  # noqa: F401  (ensures package import path)
from src.config import FACTOR_GROUPS, Config, load_config
from src.data import sector
from src.regression.rolling import factor_correlation_table
from src.regression.variance import IDIO_KEY, decompose_variance

DRIVER_FACTORS = ["market", "rates", "oil", "gas",
                  "value", "growth", "momentum", "lowvol", "quality", "credit", "metals"]


def test_drivers_factor_set_resolves_and_maps_all_proxies():
    cfg = load_config("config.yaml", tickers=["CEG"], factor_set="drivers")
    assert cfg.factor_logical == DRIVER_FACTORS
    # every active logical factor has a proxy ticker (factor_map builds with no KeyError)
    fm = cfg.factor_map
    assert set(fm) == set(DRIVER_FACTORS)
    assert fm["value"] == "IWD" and fm["credit"] == "HYG" and fm["metals"] == "DBB"
    assert cfg.use_sector is True


def test_shared_driver_groups_collapse_style_and_macro():
    groups = Config.groups_for_factors(DRIVER_FACTORS)
    assert groups["Market"] == ["market"]
    assert groups["Rates"] == ["rates"]
    assert groups["Energy"] == ["oil", "gas"]
    assert groups["Style"] == ["value", "growth", "momentum", "lowvol", "quality"]
    assert groups["Macro"] == ["credit", "metals"]
    assert "Sector" not in groups                      # sector is per-stock, not a shared factor


def test_per_stock_sector_joins_the_sector_group():
    groups = Config.groups_for_factors(DRIVER_FACTORS + ["sector"])
    assert groups["Sector"] == ["sector"]
    assert FACTOR_GROUPS["sector"] == "Sector"


def test_sector_resolver_override_and_fallback(monkeypatch):
    # known universe -> explicit override (offline, auditable)
    assert sector.sector_etf_for("CEG") == "XLU"
    assert sector.sector_etf_for("VRT") == "XLI"
    # unknown ticker -> yfinance sector mapped to the SPDR ETF
    monkeypatch.setattr(sector, "_yf_sector", lambda t: "Utilities")
    assert sector.sector_etf_for("ZZZZ") == "XLU"
    # undeterminable -> None (never fabricated)
    monkeypatch.setattr(sector, "_yf_sector", lambda t: None)
    assert sector.sector_etf_for("ZZZZ") is None
    # sector_map_for omits the unresolved names
    monkeypatch.setattr(sector, "_yf_sector", lambda t: None)
    assert sector.sector_map_for(["CEG", "ZZZZ"]) == {"CEG": "XLU"}


def _synth_frame(betas, n=300, seed=11):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    factors = {f: rng.normal(0, 0.011, n) for f in betas}
    stock = 0.0003 + sum(betas[f] * factors[f] for f in betas) + rng.normal(0, 0.006, n)
    data = {"TST": stock, **factors}
    return pd.DataFrame(data, index=idx)


def test_factor_correlation_table_shape_and_bounds():
    frame = _synth_frame({"market": 1.0, "oil": 0.3})
    tbl = factor_correlation_table(frame, "TST", ["market", "oil"], short=126, long=252)
    assert set(tbl) == {"market", "oil"}
    for f in ("market", "oil"):
        assert -1.0 <= tbl[f]["corr6m"] <= 1.0
        assert -1.0 <= tbl[f]["corr1y"] <= 1.0
    # market beta dominates -> stock should correlate more with market than with oil
    assert tbl["market"]["corr1y"] > tbl["oil"]["corr1y"]


def test_full_driver_decomposition_sums_to_one():
    betas = {f: b for f, b in zip(DRIVER_FACTORS + ["sector"],
                                  [1.1, -0.3, 0.2, 0.4, 0.5, 0.3, 0.2, 0.1, 0.2, 0.3, 0.2, 0.6])}
    frame = _synth_frame(betas)
    factor_cols = DRIVER_FACTORS + ["sector"]
    groups = Config.groups_for_factors(factor_cols)
    v = decompose_variance(frame["TST"], frame[factor_cols], groups)
    assert set(v.shares) >= {"Market", "Rates", "Energy", "Style", "Macro", "Sector", IDIO_KEY}
    assert all(s >= 0.0 for s in v.shares.values())
    assert abs(sum(v.shares.values()) - 1.0) < 1e-9
