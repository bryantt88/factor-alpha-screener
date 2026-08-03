"""FastAPI service exposing the screener to the React/Next.js front-end.

Endpoints:
  GET  /api/health              -> {"status":"ok"}
  POST /api/screen              -> run a screen, return the full JSON payload (optionally save to KB)
  GET  /api/history             -> list saved runs (meta)
  GET  /api/history/{run_id}    -> re-open a saved run's full payload

Run:  uvicorn src.api.server:app --reload --port 8000
The pipeline (src/) is unchanged — this only orchestrates run_screen + serialises. CORS is open to
localhost dev ports so the Next.js dev server can call it.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(_ROOT)  # so config.yaml + runs/ resolve at the repo root

from ..agent.exposure_agent import GRADES, TYPES, confirm_exposure
from ..agent.gemini_client import GeminiError, gemini_available
from ..app.explain import explain_stock
from ..config import load_config
from ..data.benchmark import benchmark_for_type, relative_strength
from ..gates.exposure import exposure_verdict
from ..knowledge_base import hashing, store
from ..main import run_screen
from .serialize import screen_payload

app = FastAPI(title="AI-Power Stack Screener API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"], allow_headers=["*"],
)


class ScreenRequest(BaseModel):
    tickers: list[str] = Field(default_factory=list)
    factorSet: str = "4factor"
    horizon: int = 252
    equipment: list[str] = Field(default_factory=list)
    fundamentalsSource: str = "edgar"
    sizeFloorB: float = 2.0
    name: str = ""
    save: bool = False


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "geminiAvailable": gemini_available()}


def _single_output(ticker: str, factor_set: str, horizon: int):
    """Recompute one ticker's StockOutput + its Gate-1/2 data (for explain / relative-strength — they
    need the reg object, which isn't persisted across stateless API calls). Reuses run_screen."""
    cfg = load_config("config.yaml", tickers=[ticker.upper()], factor_set=factor_set, horizon=horizon)
    res = run_screen(cfg, make_charts=False)
    return res.outputs.get(ticker.upper()), cfg, res.gates.get(ticker.upper())


@app.post("/api/screen")
def screen(req: ScreenRequest) -> dict:
    tickers = [t.strip().upper() for t in req.tickers if t.strip()]
    if not tickers:
        raise HTTPException(status_code=422, detail="Provide at least one ticker.")
    cfg = load_config("config.yaml", tickers=tickers, factor_set=req.factorSet, horizon=req.horizon,
                      fundamentals_source=req.fundamentalsSource, size_floor_usd=req.sizeFloorB * 1e9,
                      equipment_tickers=[t.strip().upper() for t in req.equipment if t.strip()])
    run_id = hashing.compute_run_id(cfg.tickers, cfg.factor_set, cfg.return_frequency,
                                    cfg.time_horizon_days, cfg.as_of_date)
    cfg.output_dir = os.path.join("runs", run_id)
    result = run_screen(cfg, make_charts=False)
    if req.save:
        store.save_run(result, run_id, name=req.name, make_charts=True)
    payload = screen_payload(result, run_id=run_id, name=req.name)
    payload["dropped"] = sorted(set(tickers) - set(cfg.tickers))
    payload["saved"] = bool(req.save)
    return payload


@app.get("/api/history")
def history() -> list[dict]:
    return [{"runId": m.get("run_id"), "name": m.get("name", m.get("run_id")),
             "asOfDate": m.get("as_of_date"), "factorSet": m.get("factor_set"),
             "horizon": m.get("time_horizon_days"), "tickers": m.get("tickers", []),
             "summary": m.get("summary", {}), "timestamp": m.get("timestamp"),
             "hasFullResult": m.get("has_full_result", False)} for m in store.list_runs()]


@app.get("/api/history/{run_id}")
def history_run(run_id: str) -> dict:
    full = store.load_full_run(run_id)
    if full is None:
        raise HTTPException(status_code=404, detail="Run not found or has no saved full result.")
    meta, _ = store.load_run(run_id)
    return screen_payload(full, run_id=run_id, name=meta.get("name", run_id))


# --- Gate 3 (AI exposure) — propose-and-approve, the only LLM decision ---------------------------
class ExposureRequest(BaseModel):
    ticker: str
    deep: bool = False             # True = live web search (~2min); False = recent-news grade (~25s)


@app.post("/api/exposure")
def exposure(req: ExposureRequest) -> dict:
    """Grade a ticker's AI-exposure story (Gemini). Proposal only — never auto-approved.
    `deep` runs live web search to catch older/structural deals; otherwise grounds in recent news."""
    if not gemini_available():
        raise HTTPException(status_code=503, detail="Gemini CLI not available in this environment.")
    p = confirm_exposure(req.ticker.strip().upper(), deep=req.deep)
    return {
        "ticker": p.ticker, "company": p.company, "type": p.type, "grade": p.grade,
        "summary": p.summary, "comment": p.comment, "nSources": p.n_sources, "mode": p.mode,
        "bullets": p.bullets, "error": p.error, "types": TYPES, "grades": GRADES,
    }


class VerdictRequest(BaseModel):
    grade: str                     # final grade (AI's proposal, or the reviewer's override)
    type: str = "unknown"
    error: str | None = None
    decision: str | None = None    # approved | rejected | None


@app.post("/api/exposure/verdict")
def exposure_verdict_ep(req: VerdictRequest) -> dict:
    """Turn the final grade + human decision into the Gate-3 verdict (rules live in Python, not the UI)."""
    v = exposure_verdict(req.grade, req.decision, type_=req.type, error=req.error)
    return {"status": v.status, "type": v.type, "note": v.note}


class RelStrengthRequest(BaseModel):
    ticker: str
    type: str
    factorSet: str = "4factor"
    horizon: int = 252


@app.post("/api/relative-strength")
def rel_strength(req: RelStrengthRequest) -> dict:
    """Output 4 — cumulative excess return vs the type's sector benchmark (auto-picked from type)."""
    o, cfg, _ = _single_output(req.ticker, req.factorSet, req.horizon)
    if o is None:
        raise HTTPException(status_code=404, detail=f"No regression data for {req.ticker}.")
    bench = benchmark_for_type(req.type, cfg.benchmark_map)
    if not bench:
        return {"benchmark": None, "series": None, "note": f"No benchmark mapped for type '{req.type}'."}
    rel = relative_strength(o.reg.stock_returns, bench)
    if rel is None or len(rel) == 0:
        return {"benchmark": bench, "series": None, "note": f"Benchmark {bench} data unavailable."}
    return {"benchmark": bench,
            "series": {"dates": [d.strftime("%Y-%m-%d") for d in rel.index],
                       "values": [float(v) for v in rel]}}


class ExplainRequest(BaseModel):
    ticker: str
    factorSet: str = "4factor"
    horizon: int = 252


@app.post("/api/explain")
def explain(req: ExplainRequest) -> dict:
    """Gemini 'how to read this' — explains the computed numbers, never invents any."""
    if not gemini_available():
        raise HTTPException(status_code=503, detail="Gemini CLI not available in this environment.")
    o, _, gate = _single_output(req.ticker, req.factorSet, req.horizon)
    if o is None:
        raise HTTPException(status_code=404, detail=f"No regression data for {req.ticker}.")
    try:
        return {"text": explain_stock(o, gate=gate)}
    except GeminiError as e:
        raise HTTPException(status_code=502, detail=f"Gemini call failed: {e}")


# --- serve the built front-end (single origin) ---------------------------------------------------
# When web/out exists (a `next build` static export), FastAPI serves the whole app at "/" so the
# deployed service is ONE URL: the page + /api together. Mounted LAST so the /api/* routes above win.
# In local dev the two servers run separately and this mount is simply absent (no build yet).
_WEB_OUT = os.path.join(_ROOT, "web", "out")
if os.path.isdir(_WEB_OUT):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_WEB_OUT, html=True), name="frontend")
