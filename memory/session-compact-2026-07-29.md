## COMPACT — 2026-07-29 (covers since 2026-07-28)

**In one line:** Built the v2 Performance-Drivers reframe end to end — a Shapley/LMG variance panel (new `drivers` factor mode), rigor upgrades (HAC SEs, adjusted R², stability), plainer wordings, and the React UI — all tested and validated on real data.

### WHAT CHANGED
- `regression/variance.py` (NEW) — Shapley/LMG variance decomposition; shares sum to 100%, idiosyncratic = 1 − adjusted R².
- `drivers` factor mode (NEW, config.py) — full JPM model: Market/Rates/Energy/Sector/Style/Macro/Idiosyncratic. Existing modes untouched.
- Per-stock Sector factor (`data/sector.py`) — each stock regressed on its own GICS SPDR ETF (XLU/XLI/…).
- Robust standard errors (Newey-West/HAC) in `engine.py` — betas/R² unchanged, only alpha t-stat/p-value.
- Adjusted R² correction — fixes overfitting bias from 12 factors; idiosyncratic no longer understated.
- Stability check — shares recomputed 6M vs 1Y; groups swinging >10pp flagged.
- Wordings simplified — verdict labels ("Rising on its own" / "Turning up underneath" / "Just riding the wave" / "No clear idiosyncratic trend"), confidence tag (Real / Not proven / Likely luck, t≥2 / 1–2 / <1). "idiosyncratic return" not "own-merit".
- React `drivers` panel (`web/components/Drivers.jsx`) — bars + 6M/1Y factor table, first/default tab. Next build passes; verified through running servers.

### WHERE THINGS STAND
- Backend + JSON carry `drivers`, `factorTable`, stability, caveats. 19/19 tests pass.
- Live reads sensibly: CEG sector-driven, VRT style-driven, Energy ~1% (no commodity ride); CVX = Reject (Energy 14%). GE 3yr = "Real" (t 2.19).

### DO NEXT
1. Optional: full vertical-card UI reframe (drop Gate 1/2/3 packaging → stacked 🔴/🟡/🟢 cards). Drivers is primary tab; gate strip still present.
- Blocked on: nothing. Macro proxies (HYG/DBB) are directional-only; FRED/breakeven deferred.

### DECISIONS LOCKED
- Energy + Rates each their own group (not folded into Macro) — the two macro drivers this universe cares about.
- Idiosyncratic = 1 − adjusted R²; LMG shares scaled to adj R² (relative split unchanged).
- t≥2 = "Real"; 1yr daily rarely clears it — a longer window is the honest path to high confidence.
