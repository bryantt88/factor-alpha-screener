# PLATFORM — the website / UI layer

This is the platform that sits on top of the pipeline. The pipeline (gates, regression, outputs, knowledge base) is specified in `SPEC.md`; this file specifies how a user *interacts* with it through a web app.

## Tech choice

**Streamlit** for v1 — Python-native, so the UI calls the same `src/` modules directly with no API boundary, and it's the fastest path to a working screening tool for a solo analyst. If it outgrows that (multi-user, auth, heavy concurrency), migrate to **FastAPI + React**; the pipeline modules don't change, only `app/` does. Local-first: runs on your machine, reads/writes the local knowledge base.

## The three pages

```
┌─ New Run ──────────┐   ┌─ Results Dashboard ─┐   ┌─ History / KB ──────┐
│ input + parameters │ → │ scorecard + 5 charts│   │ browse past runs    │
│ [Run]              │   │ + per-stock drill   │ ← │ open any saved run  │
└────────────────────┘   └─────────────────────┘   └─────────────────────┘
```

### Page 1 — New Run (input form)

The parameter bar is at the **top**, exactly as specced. All defaults pre-filled so a user can just paste tickers and hit Run.

| Control | Type | Default |
|---------|------|---------|
| Tickers | text input (space/comma separated, one or many) | — |
| **Factor mode** | toggle at the top: `4-factor` / `commodity-only` | 4-factor |
| Time horizon | slider / number (months → days) | 12 months (252d) |
| Return frequency | select | daily |
| Size floor | number | $2B |
| Fundamentals source | select: `public` / `refinitiv` | public |
| **Run** | button | — |

On Run → the pipeline executes (all gates on all tickers), with a progress indicator per stage. The agent step (Gate 3) pauses for approval — see below.

### Page 2 — Results Dashboard

The single screen that ties every output together. Layout top → bottom:

1. **Scorecard table** (from `OUTPUTS.md` §5) — one row per ticker, all four gates ✓/✗/flag with the key number, α, betas, R², p-values, raw 6m/12m return, idiosyncratic return + slope, and the **Track tag**. Sortable; default sort by cumulative idiosyncratic return. Failing gates stay visible and color-coded — never hidden. `null`/`unverified` cells render as such, never blank.
2. **Combined idiosyncratic trend** — all tickers' α+ε lines overlaid for ranking.
3. **Per-stock section** (expander per ticker) containing that stock's:
   - raw-vs-idiosyncratic chart (gap shaded, endpoints annotated, one-line verdict),
   - rolling correlation + rolling beta (decoupling),
   - return-attribution waterfall,
   - relative strength vs its type benchmark,
   - the Gate-3 **sourced exposure bullets** with clickable source links.
4. **Save to knowledge base** — button (or auto-save on completion). Dedup behavior surfaced (see below).

All charts interactive (Plotly), hover for exact values. Consistent color language across charts (idiosyncratic = one fixed color, each factor fixed, raw price neutral).

### Page 3 — History / Knowledge Base

- A searchable/sortable list of past runs: tickers, factor mode, horizon, as-of date, timestamp, and a summary (e.g. "3 Track-1, 1 Track-2").
- Click any run to reopen its **saved** dashboard — rendered from stored artifacts, so it shows what it showed *then*, even after prices have moved (the audit-trail guarantee).
- Filter by ticker ("show every run that included VST").

## The propose-and-approve loop (Gate 3)

The one human-in-the-loop step, and the hallucination guardrail made visible:

1. Pipeline reaches Gate 3 → agent retrieves and drafts sourced exposure bullets + a type classification per stock.
2. UI **pauses** and shows the draft: bullets, each with its source link, and the proposed type.
3. User **approves / edits / rejects** per stock. Only approved exposure is recorded as a Gate-3 pass.
4. Pipeline continues to the regression.

This makes the agent's output auditable before it enters the scorecard — the user confirms every AI-exposure claim against its source, so no unverified assertion silently flows through.

## Save & dedup UX

On save, compute the run hash (`SPEC.md` §8):
```
run_id = hash(sorted_tickers + factor_set + return_frequency + time_horizon + as_of_date)
```
- **New hash** → save inputs + outputs to `runs/<run_id>/`, index in SQLite.
- **Exact match exists** → do not duplicate. Show "An identical run already exists (same tickers, parameters, and data date)" and link to the existing record.
- Because `as_of_date` advances with time and horizon/factor-mode are user knobs, the *same tickers* re-run next week, or at a different horizon, or in the other factor mode, is a **new, legitimate record** — not a duplicate.

## Session & state

- Run parameters + intermediate results live in Streamlit session state during a run.
- Persistence: `runs/<run_id>/` holds serialized charts + the scorecard; SQLite (`knowledge_base/`) holds the run index (hash, params, as-of date, timestamp, summary).
- Config defaults come from `config.yaml`; the UI lets the user override per run but doesn't rewrite the config.

## Build note

This is build-order step 5 (last), on top of a working pipeline. Until it exists, the pipeline is fully usable from the CLI (`python -m src.main --tickers ... --factor-set ...`) — the UI is a convenience layer over the same modules, not a rewrite. Build the CLI path first; the Streamlit app should import and call the exact same functions.
