"""Knowledge base storage (SPEC §8): per-run artifact folders runs/<run_id>/ + a JSON meta index.

Saves inputs + outputs as computed at that moment, so a historical run always shows what it showed
then. v1 uses a meta.json per run folder (scanned to build the History list) + the scorecard CSV; the
interactive charts are already written into the same folder by viz.charts.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import pickle

import pandas as pd

from ..gates.trend import OIL_FACTOR_CAVEAT
from ..viz.charts import build_scorecard

RESULT_PICKLE = "result.pkl"   # full ScreenResult, so History can re-render the whole dashboard


def _summary(result) -> dict:
    counts: dict[str, int] = {}
    for o in result.outputs.values():
        key = o.trend.track_tag.split(" — ")[0]
        counts[key] = counts.get(key, 0) + 1
    return counts


def _data_notes(result) -> dict:
    """Data-quality caveats worth preserving in the audit trail (v1.1 oil-factor decision)."""
    notes: dict = {}
    active = set(result.config.factor_logical)
    if active & {"oil", "gas"}:
        notes["oil_factor_caveat"] = OIL_FACTOR_CAVEAT
    flagged = [t for t, o in result.outputs.items() if o.trend.tracking_noise]
    if flagged:
        notes["tracking_noise_flagged"] = flagged
    return notes


def save_run(result, run_id: str, name: str | None = None, timestamp: str | None = None,
             make_charts: bool = True) -> str:
    """Persist a run to its folder: meta.json + scorecard.csv + a pickled full ScreenResult (so
    History can re-render the entire dashboard, not just the snapshot). Opt-in — called only when the
    user clicks 'Add to Knowledge Base'. Returns the run folder path.

    `name` is a human label (the run_id stays the dedup hash). `make_charts` also writes the standalone
    interactive HTML charts into the folder (skipped if they were never generated)."""
    os.makedirs(result.output_dir, exist_ok=True)
    cfg = result.config
    meta = {
        "run_id": run_id,
        "name": (name or "").strip() or run_id,
        "tickers": list(cfg.tickers),
        "equipment_tickers": list(getattr(cfg, "equipment_tickers", [])),
        "factor_set": cfg.factor_set,
        "time_horizon_days": cfg.time_horizon_days,
        "return_frequency": cfg.return_frequency,
        "as_of_date": cfg.as_of_date.isoformat(),
        "timestamp": timestamp or _dt.datetime.now().isoformat(timespec="seconds"),
        "summary": _summary(result),
        "data_notes": _data_notes(result),
        "skipped": result.skipped,
        "output_dir": result.output_dir,
        "has_full_result": True,
    }
    with open(os.path.join(result.output_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    if result.gates or result.outputs:
        build_scorecard(result).to_csv(
            os.path.join(result.output_dir, "scorecard.csv"), index=False)
    # Full result for exact re-render. Pickle can fail on odd objects — never let it break the save.
    try:
        with open(os.path.join(result.output_dir, RESULT_PICKLE), "wb") as f:
            pickle.dump(result, f)
    except Exception:
        meta["has_full_result"] = False
        with open(os.path.join(result.output_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    if make_charts and result.outputs:
        from ..viz import charts
        charts.chart_raw_vs_idiosyncratic(result.outputs, result.output_dir)
        charts.chart_rolling_decoupling(result.outputs, result.output_dir)
        charts.chart_attribution_waterfall(result.outputs, result.output_dir)
        charts.save_detail_table(result.outputs, result.output_dir)
    return result.output_dir


def load_full_run(run_id: str, runs_dir: str = "runs"):
    """Return the pickled ScreenResult for a saved run, or None if absent/unreadable (older runs,
    or a cross-version pickle mismatch — callers fall back to the scorecard CSV)."""
    path = os.path.join(runs_dir, run_id, RESULT_PICKLE)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "rb") as f:
            return pickle.load(f)
    except Exception:
        return None


def run_exists(run_id: str, runs_dir: str = "runs") -> bool:
    return os.path.isfile(os.path.join(runs_dir, run_id, "meta.json"))


def list_runs(runs_dir: str = "runs") -> list[dict]:
    """All saved runs (most recent first), each the meta.json dict + a `folder` key."""
    out = []
    if not os.path.isdir(runs_dir):
        return out
    for name in os.listdir(runs_dir):
        mp = os.path.join(runs_dir, name, "meta.json")
        if os.path.isfile(mp):
            try:
                with open(mp, encoding="utf-8") as f:
                    meta = json.load(f)
                meta["folder"] = os.path.join(runs_dir, name)
                out.append(meta)
            except Exception:
                continue
    return sorted(out, key=lambda m: m.get("timestamp", ""), reverse=True)


def load_run(run_id: str, runs_dir: str = "runs") -> tuple[dict, pd.DataFrame | None]:
    """Return (meta, scorecard_df) for a saved run; df is None if no scorecard was written."""
    folder = os.path.join(runs_dir, run_id)
    with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    csv = os.path.join(folder, "scorecard.csv")
    df = pd.read_csv(csv) if os.path.isfile(csv) else None
    return meta, df


# --- backtest knowledge base (separate from screen runs) -----------------------------------------
# Backtest payloads are already JSON-safe (built in api/serialize + server), so we persist one JSON
# file per saved backtest in backtests/. Id is a content hash of (universe + params) so re-saving the
# same configuration overwrites its slot (dedup), like the screen run_id.
BACKTESTS_DIR = "backtests"


def _backtest_id(payload: dict) -> str:
    import hashlib
    key = json.dumps({"stocks": sorted(payload.get("stocks", [])),
                      "factors": sorted(payload.get("factors", [])),
                      "params": payload.get("params", {})}, sort_keys=True)
    return "bt_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def save_backtest(payload: dict, name: str = "", timestamp: str | None = None,
                  runs_dir: str = BACKTESTS_DIR) -> str:
    """Persist a backtest result (opt-in). Returns its id. Stores headline stats for the list plus the
    full payload for exact re-render."""
    os.makedirs(runs_dir, exist_ok=True)
    bid = _backtest_id(payload)
    neutral = payload.get("neutral", {}) or {}
    stats = payload.get("stats", {}) or {}
    rec = {
        "id": bid,
        "name": (name or "").strip() or bid,
        "timestamp": timestamp or _dt.datetime.now().isoformat(timespec="seconds"),
        "stocks": payload.get("stocks", []),
        "factors": payload.get("factors", []),
        "params": payload.get("params", {}),
        "summary": {
            "totalReturn": neutral.get("totalReturn"), "cagr": neutral.get("cagr"),
            "annVol": neutral.get("annVol"), "maxDrawdown": neutral.get("maxDrawdown"),
            "sharpe": neutral.get("sharpe"), "realizedMarketBeta": stats.get("realizedMarketBeta"),
        },
        "payload": payload,
    }
    with open(os.path.join(runs_dir, bid + ".json"), "w", encoding="utf-8") as f:
        json.dump(rec, f)
    return bid


def list_backtests(runs_dir: str = BACKTESTS_DIR) -> list[dict]:
    """Saved backtests (most recent first): id, name, timestamp, universe size, params, headline stats."""
    out = []
    if not os.path.isdir(runs_dir):
        return out
    for fn in os.listdir(runs_dir):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(runs_dir, fn), encoding="utf-8") as f:
                rec = json.load(f)
            out.append({k: rec.get(k) for k in ("id", "name", "timestamp", "stocks", "factors",
                                                "params", "summary")})
        except Exception:
            continue
    return sorted(out, key=lambda m: m.get("timestamp", ""), reverse=True)


def load_backtest(bid: str, runs_dir: str = BACKTESTS_DIR) -> dict | None:
    """Return the full saved backtest payload, or None if absent/unreadable."""
    path = os.path.join(runs_dir, bid + ".json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f).get("payload")
    except Exception:
        return None
