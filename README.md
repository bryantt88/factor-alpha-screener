---
title: AI Power Screener
emoji: ⚡
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# AI-Power Stack Screener

A screening + regression tool for finding mid-to-large-cap, US-listed **AI-power-stack** equities — power generators and power/data-center equipment makers — that are (1) the right size, (2) genuinely exposed to AI data-center demand, (3) fundamentally sound, and (4) on a real *idiosyncratic* uptrend once commodity and market noise is stripped out.

It is built around one core idea from the original mandate:

> A power stock can rise just because oil and gas rose. We want the stocks that rise **by more than commodities alone can explain** — the ones with a genuine, structural AI tailwind. A rolling regression strips out the commodity (and market/rate) component; what's left — **alpha + residual** — is the stock's own trend.

## What it does

You paste one or more tickers. Every ticker is run through **every gate** and scored on a scorecard (nothing is silently dropped — you see exactly which gates each name passes and fails). The regression runs on all of them, producing a set of informative charts and a ranked summary table, and the whole run is saved to a local knowledge base so you can revisit historical runs.

## The four gates

| Gate | Question | How it's answered |
|------|----------|-------------------|
| 1. Size | Mid-to-large cap? | Deterministic — market cap vs floor (default $2B) |
| 2. Fundamentals | Profitable, beating, sensibly valued? | Deterministic — a lean, decision-relevant metric set |
| 3. AI exposure | Real, contracted data-center demand? | AI agent — sourced point-form summary + type classification |
| 4. Idiosyncratic uptrend | Rising on its own merits, not commodity luck? | The regression — cumulative idiosyncratic return (α + ε) |

## Quick start

```bash
# 1. environment
python -m venv .venv && source .venv/bin/activate   # or: uv venv / conda
pip install -r requirements.txt

# 2. run the regression engine on a watchlist (built first, works standalone)
python -m src.main --tickers VST CEG NRG VRT ETN --factor-set 4factor --horizon 252

# 3. later: full scorecard + agent + knowledge base
```

## Documentation

Read these in order. `docs/SPEC.md` is the source of truth for the whole design.

| File | Contents |
|------|----------|
| `CLAUDE.md` | Operating rules for Claude Code — read this every session |
| `docs/SPEC.md` | Full design: architecture, gates, metrics, knowledge base, agent, repo layout, build order |
| `docs/REGRESSION.md` | The regression math — formula, beta estimation, windows, the α + ε convention, both factor modes |
| `docs/OUTPUTS.md` | The five outputs and how to make each one genuinely informative |
| `docs/DATA.md` | Data sourcing — public-first, Refinitiv as a swappable one-time backend |
| `docs/PLATFORM.md` | The website/UI layer — pages, user flow, factor toggle, results dashboard, approve loop, history browser |
| `docs/UNIVERSE.md` | Domain context — the buckets, candidate names, and why some were ruled out |

## Build order (back-to-front)

1. **Regression engine** — standalone, on free public price data. The core.
2. **Gates / scorecard** — wrap the engine.
3. **Data layer** — fundamentals backend (public first, Refinitiv slot-in).
4. **AI-exposure agent** — Stage 3, propose-and-approve with sources.
5. **Knowledge base + UI** — the platform layer.

## Non-negotiable principle

The LLM/agent is used for **exactly one thing**: reading unstructured text (filings, press releases, earnings calls) to confirm AI exposure — and it must cite a source for every claim. Every *number* (market cap, margins, betas, returns) comes from real data or deterministic computation. No model ever fabricates a figure. See `CLAUDE.md`.
