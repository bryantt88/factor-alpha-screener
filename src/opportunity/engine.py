"""Factor-model opportunity engine (P0) — reads each stock's idiosyncratic gap and turns it into
actionable, threshold-gated trade ideas. NOTHING here fits a new model; it only reads the numbers the
regression + Shapley variance decomposition already produced (CLAUDE.md rule 2: never fabricate).

The thesis in one line: a stock's return = factor-explained part + its own-story gap (α+ε). We want
the names whose gap is REAL and positive (own-merit alpha), we want to fade the ones whose gap is a
factor ride dressed up as alpha, and we want to hold that alpha with the factor risk hedged out.

Two axes → four descriptive buckets (per stock):
  • Core long        — idio gap positive AND statistically real (alpha tier 'Real'), not tracking-noise.
  • Rich / crowded   — idio gap positive BUT not backed by real alpha (or flagged tracking-noise) → fade.
  • Cheap to factors — idio gap negative while the stock has real factor exposure → lagging its factors,
                       a mean-reversion WATCH (not a committed long).
  • No signal        — |gap| within the dead-band → the return is essentially just factor beta.

Trade ideas (the filtered, high-conviction set — the whole point of "just show the good trade"):
  • Directional longs — Core-long names that also clear the information-ratio bar.
  • Neutral pairs     — long a real-alpha name / short a same-factor 'rich' name, sized so the SHARED
                        factor exposure nets to ~0 (matched hedge ratio). Only when the two profiles
                        genuinely overlap; otherwise no pair is offered (never forced).
  • Factor-hedged book— the general construction that works for ANY basket, even unrelated names: long
                        the qualifying names, short the factor-proxy ETFs sized to zero the book's net
                        factor exposure.
If nothing clears the bar → `none=True` with the honest message. A tool a PM trusts must be willing to
say "no trade here".

Thresholds are named module constants (mirroring gates/trend.py's local style), not scattered literals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite

# --- decision thresholds (tuneable in one place) -------------------------------------------------
OPP_DEADBAND = 0.02        # |cumulative idiosyncratic α+ε| below this = "no gap" (matches trend.py)
OPP_MIN_IR = 0.5           # a directional long must clear this annualised information ratio
CHEAP_MIN_R2 = 0.30        # "cheap to factors" needs the factors to explain ≥30% (something to revert to)
PAIR_MIN_COS = 0.50        # min cosine similarity of the two beta vectors for a pair to be "clean"
PAIR_MIN_BETA = 0.10       # the shared hedge factor must carry at least this |beta| in BOTH legs
PAIR_MAX_RATIO = 8.0       # reject degenerate hedge ratios (one leg dwarfs the other)
HEDGE_MIN_NET_BETA = 0.05  # only hedge a factor whose net book exposure exceeds this

# Style + sector factors are mutually collinear (all large-cap US equity baskets), so their PARTIAL
# betas are unstable/inflated (a stock can show β −2.5 on low-vol while barely correlating with it).
# They are therefore NEVER read to the user as an exposure, and NEVER used to size a hedge — we hedge
# on the non-collinear macro factors (market, rates, energy, fx, …) whose betas are stable.
NON_HEDGE_FACTORS = {"value", "growth", "momentum", "lowvol", "quality", "sector"}

# Plain-language bucket labels (shown to the user). Internal logic keys off these constants.
BUCKET_CORE = "Rising on its own"      # own gains are real → candidate long
BUCKET_RICH = "Just riding factors"    # up, but only from market/sector/commodity → fade
BUCKET_CHEAP = "Lagging its factors"   # fell more than its factors justify → possible bounce, watch
BUCKET_NONE = "No clear edge"          # return is basically just factor/market movement


@dataclass
class KillRisk:
    """The driver GROUP explaining the most of a stock's NON-idiosyncratic risk — what you're
    accidentally betting on, from the Shapley variance split (collinearity-robust). We deliberately do
    NOT surface a single partial beta here (those can be suppressor artifacts under collinearity)."""
    group: str | None
    share: float | None        # that group's share of return variance (0..1), None if unavailable
    factor: str | None = None  # kept for payload compatibility; not shown (unreliable individually)
    beta: float | None = None


@dataclass
class StockRead:
    ticker: str
    bucket: str
    idio: float                # compounded cumulative idiosyncratic α+ε (the gap)
    ir: float | None           # information ratio (annualised alpha / idiosyncratic vol)
    tstat: float | None        # alpha t-stat (is the gap real?)
    tier: str                  # "Real" | "Not proven" | "Likely luck"
    raw: float                 # compounded raw return over the window
    r2: float
    noisy: bool                # tracking-noise flag (idio may be inflated by proxy roll/non-sync)
    qualifies_long: bool
    kill_risk: KillRisk | None
    note: str
    signal: dict | None = None    # recent (short-window) idiosyncratic trajectory — the fast timing read


@dataclass
class Pair:
    long: str
    short: str
    factor: str                # the shared factor the hedge neutralises
    hedge_ratio: float         # short this many units of `short` per 1 unit long of `long`
    cos: float                 # beta-vector overlap (pair "cleanliness")
    long_idio: float
    short_idio: float
    note: str


@dataclass
class HedgeLeg:
    ticker: str
    weight: float              # signed: + = long, − = short (per 1.0 of total long book)
    kind: str                  # "stock" | "factor"
    label: str = ""


@dataclass
class HedgedBook:
    longs: list[HedgeLeg]
    hedges: list[HedgeLeg]
    unhedged: list[str] = field(default_factory=list)  # factors we couldn't hedge (no single proxy)
    note: str = ""


@dataclass
class Opportunities:
    reads: list[StockRead]
    longs: list[str]           # tickers that clear the directional-long bar (best IR first)
    pairs: list[Pair]
    book: HedgedBook | None
    none: bool                 # True => nothing cleared the bar
    message: str


# --- helpers -------------------------------------------------------------------------------------
def _finite(x) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if isfinite(f) else None


def _kill_risk(o) -> KillRisk | None:
    """The driver GROUP that explains most of the stock's factor risk (top Shapley variance share).
    Collinearity-robust — deliberately NOT the largest partial beta, which can be a suppressor artifact
    (e.g. a huge low-vol β on a stock that barely correlates with low-vol)."""
    v = getattr(o, "variance", None)
    if v is not None:
        for g, share in v.ordered():
            if g == v.idio_key:
                continue
            return KillRisk(group=g, share=_finite(share))
    return None


def _hedge_betas(reg) -> dict:
    """Betas to use for HEDGING — never the collinear style/sector partials. When the residuals are
    available we refit on just the non-collinear macro factors (stable betas); otherwise we fall back
    to the existing betas with the style/sector factors dropped."""
    fr = getattr(reg, "factor_returns", None)
    if fr is not None and hasattr(fr, "columns") and hasattr(reg, "stock_returns"):
        keep = [c for c in fr.columns if c not in NON_HEDGE_FACTORS]
        if keep:
            try:
                from ..regression.engine import run_regression
                return dict(run_regression(reg.stock_returns, fr[keep]).betas)
            except Exception:
                pass
    return {f: b for f, b in (getattr(reg, "betas", {}) or {}).items() if f not in NON_HEDGE_FACTORS}


def _recent_signal(o, window: int) -> dict | None:
    """Fast timing read: the idiosyncratic (α+ε) trajectory over just the last `window` days, using the
    residuals from the STABLE risk-window regression (so the hedge stays put while the signal moves).
    `state`: opening = own-story gap widened recently, closing = it gave back, flat = neither."""
    idio = getattr(o.reg, "idio", None)
    if idio is None or len(idio) == 0:
        return None
    recent = idio.tail(window) if window and window > 0 else idio
    if len(recent) == 0:
        return None
    comp = float((1.0 + recent).prod() - 1.0)
    slope_ann = float(recent.mean() * 252)
    state = "improving" if comp > OPP_DEADBAND else ("weakening" if comp < -OPP_DEADBAND else "flat")
    return {"window": int(len(recent)), "recentIdio": comp, "recentSlopeAnn": slope_ann, "state": state}


def _bucket(o) -> str:
    """Category from the own-story sign + whether the alpha is statistically real. Tracking-noise is
    NOT a demoter here (it's surfaced separately as a ⚠ flag) — otherwise drivers mode, where high R²
    is normal, would mislabel almost everything as 'just riding factors'."""
    idio = o.trend.idio_endpoint
    tier = o.trend.alpha_tier
    if idio > OPP_DEADBAND and tier == "Real":
        return BUCKET_CORE
    if idio > OPP_DEADBAND:
        return BUCKET_RICH
    if idio < -OPP_DEADBAND and o.reg.r2 >= CHEAP_MIN_R2:
        return BUCKET_CHEAP
    return BUCKET_NONE


def _note(bucket: str, o, kr: KillRisk | None) -> str:
    idio, tier, t = o.trend.idio_endpoint, o.trend.alpha_tier, o.trend.alpha_tstat
    risk = ""
    if kr and kr.group:
        risk = (f" Biggest exposure: {kr.group}"
                + (f" ({kr.share * 100:.0f}% of its risk)." if kr.share is not None else "."))
    if bucket == BUCKET_CORE:
        return (f"Its own gains are genuine and statistically real (t {t:+.1f}; own-story {idio:+.0%} "
                f"over the risk window) — a candidate long.{risk}")
    if bucket == BUCKET_RICH:
        return (f"Up {idio:+.0%}, but that's mostly the market/sector/commodity carrying it, not its "
                f"own strength ({tier}) — fade / avoid.{risk}")
    if bucket == BUCKET_CHEAP:
        return (f"It has fallen more than its factors justify (own-story {idio:+.0%}) — a possible "
                f"bounce, worth watching (not a committed long yet).{risk}")
    return "The move is basically just market/factor beta — no real own-story edge here."


def _cos(a: dict, b: dict) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = sum(a.get(k, 0.0) ** 2 for k in keys) ** 0.5
    nb = sum(b.get(k, 0.0) ** 2 for k in keys) ** 0.5
    return dot / (na * nb) if na > 0 and nb > 0 else 0.0


def _shared_hedge_factor(bl: dict, bs: dict) -> str | None:
    """Factor both legs load on with the SAME sign and enough magnitude — the one whose exposure a
    long/short cancels. Pick the largest common exposure (geometric mean of |betas|)."""
    best, best_score = None, 0.0
    for f in set(bl) & set(bs):
        if f in NON_HEDGE_FACTORS:                      # never hedge on a collinear style/sector beta
            continue
        x, y = bl.get(f, 0.0), bs.get(f, 0.0)
        if x == 0 or y == 0 or (x > 0) != (y > 0):     # need same sign to hedge
            continue
        if abs(x) < PAIR_MIN_BETA or abs(y) < PAIR_MIN_BETA:
            continue
        score = (abs(x) * abs(y)) ** 0.5
        if score > best_score:
            best, best_score = f, score
    return best


def _build_pairs(reads: dict[str, StockRead], regs: dict) -> list[Pair]:
    """Long a Core-long name / short a Rich-crowded name that shares a dominant factor, sized so the
    shared factor nets to ~0. Only clean, non-degenerate pairs are returned (else none)."""
    longs = [t for t, r in reads.items() if r.bucket == BUCKET_CORE]
    shorts = [t for t, r in reads.items() if r.bucket == BUCKET_RICH]
    cands: list[Pair] = []
    for L in longs:
        for S in shorts:
            bl, bs = regs[L].betas, regs[S].betas
            f = _shared_hedge_factor(bl, bs)
            if f is None:
                continue
            cos = _cos(bl, bs)
            if cos < PAIR_MIN_COS:
                continue
            w = bl[f] / bs[f]                          # short w units of S per 1 unit long L
            if not (1.0 / PAIR_MAX_RATIO <= w <= PAIR_MAX_RATIO):
                continue
            note = (f"Long {L} / short {w:.2f}× {S} neutralises the shared {f} exposure "
                    f"(β {bl[f]:+.2f} vs {bs[f]:+.2f}). Keeps {L}'s real alpha "
                    f"({reads[L].idio:+.0%}) against {S}'s factor ride ({reads[S].idio:+.0%}).")
            cands.append(Pair(long=L, short=S, factor=f, hedge_ratio=float(w), cos=float(cos),
                              long_idio=reads[L].idio, short_idio=reads[S].idio, note=note))
    cands.sort(key=lambda p: p.cos, reverse=True)
    return cands[:2]                                    # top 2 cleanest, don't spam


def _build_book(long_tickers: list[str], regs: dict, factor_map: dict) -> HedgedBook | None:
    """Factor-hedged book: equal-weight the qualifying longs, then short/long factor-proxy ETFs sized
    to zero the book's AVERAGE factor exposure. Works for any basket (related or not). Factors with no
    single tradeable proxy (e.g. per-stock 'sector') can't be hedged — reported as `unhedged`."""
    if not long_tickers:
        return None
    n = len(long_tickers)
    w = 1.0 / n
    longs = [HedgeLeg(ticker=t, weight=w, kind="stock") for t in long_tickers]

    net: dict[str, float] = {}
    for t in long_tickers:
        for f, b in _hedge_betas(regs[t]).items():     # stable macro betas only (no collinear styles)
            net[f] = net.get(f, 0.0) + w * float(b)

    hedges, unhedged = [], []
    for f, nb in sorted(net.items(), key=lambda kv: -abs(kv[1])):
        if abs(nb) < HEDGE_MIN_NET_BETA:
            continue
        proxy = factor_map.get(f)
        if not proxy:
            unhedged.append(f)
            continue
        hedges.append(HedgeLeg(ticker=proxy, weight=float(-nb), kind="factor", label=f))
    note = (f"Long {n} name(s) equal-weight; short/long the macro factor proxies (market, rates, "
            f"energy…) so the book's net factor exposure is ~0 — what's left is the stock-picking. "
            f"Collinear style factors are excluded from the hedge (their betas are unstable).")
    if unhedged:
        note += (f" Not hedged (no single proxy): {', '.join(unhedged)} — residual exposure remains "
                 f"there.")
    return HedgedBook(longs=longs, hedges=hedges, unhedged=unhedged, note=note)


def build_opportunities(result) -> Opportunities:
    """Main entry: read a ScreenResult's per-stock outputs into buckets + threshold-gated trades."""
    outputs = result.outputs
    factor_map = getattr(result.config, "factor_map", {}) or {}
    signal_window = int(getattr(result.config, "signal_horizon_days", 63) or 63)

    reads: dict[str, StockRead] = {}
    for t, o in outputs.items():
        kr = _kill_risk(o)
        bucket = _bucket(o)
        ir = _finite(o.trend.information_ratio)
        qualifies = bucket == BUCKET_CORE and ir is not None and ir >= OPP_MIN_IR
        reads[t] = StockRead(
            ticker=t, bucket=bucket, idio=float(o.trend.idio_endpoint), ir=ir,
            tstat=_finite(o.trend.alpha_tstat), tier=o.trend.alpha_tier,
            raw=float(o.trend.raw_endpoint), r2=float(o.reg.r2),
            noisy=bool(o.trend.tracking_noise), qualifies_long=qualifies, kill_risk=kr,
            note=_note(bucket, o, kr), signal=_recent_signal(o, signal_window),
        )

    regs = {t: outputs[t].reg for t in outputs}
    # directional longs, best information ratio first
    long_tickers = sorted((t for t, r in reads.items() if r.qualifies_long),
                          key=lambda t: reads[t].ir, reverse=True)
    pairs = _build_pairs(reads, regs)
    book = _build_book(long_tickers, regs, factor_map)

    none = not long_tickers and not pairs
    if none:
        message = ("No trade idea meets the bar — no name shows a real, positive own-story gain with "
                   "enough conviction, and no clean pair exists in this basket.")
    else:
        bits = []
        if long_tickers:
            bits.append(f"{len(long_tickers)} directional long(s)")
        if pairs:
            bits.append(f"{len(pairs)} neutral pair(s)")
        message = "Actionable: " + ", ".join(bits) + "."
    # reads ordered by IR desc (NaN/None last), for a stable, decision-first table
    ordered = sorted(reads.values(),
                     key=lambda r: (r.ir is not None, r.ir if r.ir is not None else float("-inf")),
                     reverse=True)
    return Opportunities(reads=ordered, longs=long_tickers, pairs=pairs, book=book,
                         none=none, message=message)
