## COMPACT — 2026-07-22

### WHAT CHANGED THIS SESSION
- Took project from docs-only → working platform: all 5 build steps + Streamlit UI, end to end.
- Scaffolded workspace to SPEC §10; wired in-repo `memory/` + `.claude/commands/` (retargeted `/pm-review`, `/short-code` to this project).
- Built regression core (α+ε), Gates 1–4, refinitiv backend, Gate-3 Gemini agent, KB, Streamlit app.
- UX round: added regression-fit plot; moved per-stock charts into tabs; Gate-3 agent now gives its own "view"; standardized on ONE return convention (compounding).
- Oil-beta investigation (CVX, USO): confirmed NO engine bug; added β columns to scorecard + static reference lines on rolling chart + explanatory captions.

### CODE STATE
- `src/regression/engine.py` — OLS; `idio=α+ε`; additive AND compounded cumulatives; `predicted`.
- `src/regression/rolling.py` — static headline corr/beta + short rolling (univariate).
- `src/regression/attribution.py` — additive slices (the one additive place).
- `src/gates/{size,fundamentals,exposure,trend}.py` — 4 gates; verdicts pass/flag/fail/pending/unverified.
- `src/data/{prices,market_cap,benchmark}.py`, `fundamentals/{base,public,refinitiv}.py` + `get_backend()`.
- `src/agent/{gemini_client,exposure_agent}.py` — $0 gemini subprocess; Gate-3 grounded in real yfinance news, cited URLs enforced ∈ provided set.
- `src/viz/{charts,figures}.py` — scorecard (now WITH betas) + all figures incl. regression-fit + relative-strength.
- `src/app/ui.py` — 3 pages (New Run/Results/History), propose-and-approve, "how to read" + agent view.
- `tests/test_engine.py` — 4 offline correctness tests PASS.

### CONFIG SNAPSHOT
factor_set_default=4factor; time_horizon_days=252; corr_headline_days=252; rolling_corr_days=63; rolling_beta_days=90; oil=CL=F gas=NG=F market=SPY rates=TLT; size_floor=2e9; leverage_flag=6.0; fundamentals_source=public.

### RESULTS (sanity, as-of 2026-07-21 window)
- CEG nuclear: β_oil≈0, raw −18%, idio −36% → Neutral (de-rating).
- BE: Track 1, idio +190%, β_mkt 4.5 (violent). ROK: Track 1 but idio +5% (mostly market rider).
- Oil-beta ladder correct: USO 0.74 (corr .89) ≫ OXY .38 > DVN .34 > XLE/HAL/CVX ~.22.

### BLOCKERS & OPEN QUESTIONS
- **Oil factor CL=F** has roll artifacts + non-synchronous close (future ~2:30pm vs equity 4pm) → beta attenuation + inflated idiosyncratic. USO stress-test: +38% spurious idio (USO +70% vs CL=F +26% cumulatively). DECIDE: roll-adjusted crude series / UI caveat / leave. **User was mid-decision.**
- Gemini CLI has no live web search here → Gate-3 limited to recent yfinance news coverage.
- Real Refinitiv CSV not yet provided (public fundamentals partly unverified).

### NEXT SESSION — DO FIRST
1. Resolve the oil-factor decision above (my rec: add UI caveat now; roll-adjusted series later).
2. Optional polish: colour scorecard gate cells; "trust the static beta" note on Decoupling tab; "Run Gate 3 for all tickers" batch button.
3. Launch app: `streamlit run src/app/ui.py` → http://localhost:8501.

### DECISIONS LOCKED (do not revisit without reason)
- Idiosyncratic = α+ε always (never bare ε). User-facing convention = COMPOUNDING everywhere; attribution stays additive (labeled "additive breakdown").
- UI = Streamlit (tool goes to Bryant's boss); Reflex = migration target; pipeline is framework-agnostic.
- LLM confirms TEXT only, never numbers; Gate-3 propose-and-approve; cited sources enforced ∈ real news URLs.
- Static 252d beta is the number to trust; rolling beta is a directional diagnostic (denominator = oil variance).
- Never fabricate → null/unverified surfaced. Futures not ETFs; never WTI+Brent together.
