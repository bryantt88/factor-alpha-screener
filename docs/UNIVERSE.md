# UNIVERSE — domain context

Background so Claude Code understands the problem space. **This is context, not a hardcoded list** — the tool screens whatever tickers the user inputs. The figures here are as of mid-2026 and illustrative; the tool always pulls live data. GE Vernova (GEV) is **excluded** throughout (the desk already holds a position).

## The AI-power stack

Energy flows from fuel to the AI chip across three tiers:

- **Upstream — generation & fuel:** IPPs and utilities (nuclear, gas, renewables, geothermal).
- **Midstream — grid & transport:** high-voltage lines, substations, pipelines.
- **Downstream — data-center electrical & thermal:** transformers, switchgear, UPS, liquid cooling.

The project focuses on two buckets:
- **Bucket 1 — power generators** (sell electricity).
- **Bucket 2 — power/data-center equipment** (sell hardware — includes GEV-type generation/grid gear).

## Commodity benchmarks (the regression factors)

| Term | What it is | Ticker used |
|------|-----------|-------------|
| Henry Hub | US natural gas benchmark; sets marginal wholesale power price in most US grids | `NG=F` |
| WTI | US crude oil benchmark; drives macro energy sentiment | `CL=F` |

Gas-fired producers earn on the spark spread → high gas sensitivity. Nuclear has near-zero fuel cost but still benefits when gas sets a higher wholesale price. Regulated utilities pass fuel through → ~zero commodity sensitivity. Equipment makers → ~zero (revenue driven by capex/backlog, not spot prices).

## The central structural insight

There is an inverse relationship between "clean AI exposure + strong fundamentals" and "commodity-regression relevance":

- The names where the **commodity** strip truly bites are a small, near-closed set: **merchant gas/nuclear IPPs**.
- Almost everything else with strong AI exposure (regulated utilities, renewable yieldcos, geothermal) is **rate-driven**, so the commodity betas are ~0 and the value shifts to the market/rate factors and relative strength. This is why the `4factor` mode exists and is the default.

## Bucket 1 — generator candidates (illustrative)

| Ticker | Type | AI exposure (as of mid-2026) | Commodity-regression fit | Note |
|--------|------|------------------------------|--------------------------|------|
| VST | merchant gas + nuclear | Signed Meta + AWS PPAs; gas acquisitions | High | Strong fundamentals; de-rated in 2026 (may show as Track-2) |
| NRG | merchant gas | Contracted DC capacity + LOIs; gas JV; LS Power deal | High | Gas-heavy — best commodity-regression fit |
| CEG | nuclear | Microsoft/Meta/CyrusOne PPAs; Calpine acquisition | Moderate | Premium valuation; de-rated ~25% off 2025 high |
| TLN | nuclear + gas | ~$18B AWS PPA at Susquehanna | Moderate | Purest AI link but leveraged / GAAP-loss — user dropped it |
| PEG | regulated + nuclear | Nuclear marketed but **no signed AI deal** | ~Zero | Fails AI-exposure gate as a live pick |
| NEE | regulated + renewables | Google nuclear PPA + Meta 2.5 GW | ~Zero (rate-driven) | Mega-cap, strong; needs 4factor mode |
| AEP | regulated | 63 GW contracted load (~90% data centers) | ~Zero | Strong regulated fundamentals |
| CWEN | renewable yieldco | 1.24 GW Google PPAs | ~Zero (bond proxy) | ~$7B; yieldco leverage |
| ORA | geothermal | Google up to 150 MW (pending) + Switch ~13 MW | ~Zero | Novel "clean firm" angle; AI volume still small/early |

## Bucket 2 — equipment candidates (illustrative)

US-listed, mid-to-large cap, data-center power/thermal or grid/generation hardware. No commodity regression needed (betas ~0); evaluated on the market/sector-adjusted residual + relative strength + backlog/book-to-bill (the AI-exposure agent's job).

- **VRT** (Vertiv) — cooling / UPS; strong backlog + book-to-bill.
- **ETN** (Eaton) — electrical infrastructure; data-center order/backlog surge.
- **HUBB** (Hubbell) — grid/utility components.
- **TT** (Trane) — data-center chillers.
- **MOD** (Modine) — direct-to-chip liquid cooling.
- **POWL** (Powell) — switchgear/substations (~$8B, smallest — borderline mid-cap).
- **PWR** (Quanta) — transmission construction.
- **NVT** (nVent) — electrical connection/protection.

## Explicitly ruled out (and why)

- **AES** — a PE consortium (GIP/BlackRock, EQT, CalPERS, QIA) agreed to take it private at **$15/share** (announced March 2026, close late-2026/early-2027). Now trades on the deal spread, not on AI or commodities → regression is meaningless. Uninvestable here despite the largest hyperscaler book (~10.1 GW).
- **SMR pure-plays** (OKLO, SMR/NuScale, LEU, BWXT, Nano) — mostly pre-revenue or small-cap; fail the size + fundamentals gates despite hyperscaler interest.
- **PEG** — no signed AI contract → fails the AI-exposure gate as a live pick (keep only as a control if desired).
- **GEV** — excluded (existing desk position).

## How the tool uses this

None of the above is hardcoded. The user pastes tickers; the agent classifies each into a type; the scorecard + regression evaluate each on its merits. This file exists so Claude Code (and the user) has the domain grounding to sanity-check results — e.g. to recognize that a near-zero commodity beta on a regulated utility is *expected*, not a bug, and that a beaten-down merchant IPP with a rising idiosyncratic line is the Track-2 setup worth flagging.
