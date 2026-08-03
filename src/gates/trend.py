"""Gate 4 — Idiosyncratic uptrend. Wraps the regression into a gate + Track tag (SPEC §3, §6).

Pass = positive endpoint on the cumulative idiosyncratic (alpha+epsilon) line.
Track tag (computable from price alone, so available from Step 1):
    raw up   + idio up         -> Track 1  (confirmed winner)
    raw !up  + idio up         -> Track 2  (turn candidate)   <- surfaced though raw trend fails
    raw up   + idio !up        -> Reject   (fake AI play / commodity rider)
    otherwise                  -> Neutral
"up/down/flat" uses the cumulative endpoint sign with a small dead-band.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..regression.engine import RegressionResult

# Plain-language verdict labels (no "Track 1/2" jargon — a PM reads these directly).
# Format is "SHORT — one-line meaning"; the SHORT drives the colour language in viz/charts.
TRACK_1 = "Rising on its own — real idiosyncratic strength"
TRACK_2 = "Turning up underneath — price down but idiosyncratic return rising"
REJECT = "Just riding the wave — up, but no idiosyncratic gain"
NEUTRAL = "No clear idiosyncratic trend"

# --- tracking-noise diagnostic (oil-factor quality; CLAUDE.md v1.1 decision 2026-07-23) -----------
# CL=F is a continuous front-month future: monthly roll artifacts + a non-synchronous close (the
# future settles ~2:30pm ET vs the 4pm equity close) attenuate the fitted oil/gas betas. Attenuated
# betas leave real factor-driven moves in the residual, which inflates the cumulative idiosyncratic
# (alpha+eps). The signature: a LARGE idiosyncratic endpoint sitting on a HIGH R2 — i.e. the factors
# already explain most of the daily variance, yet the cumulative own-story is big. That combination
# is more likely factor-tracking drift (roll/non-sync) than a genuine idiosyncratic trend, so it is
# flagged, not hidden. Read the idiosyncratic return ALONGSIDE R2 (never fabricate — this only warns).
IDIO_MAGNITUDE_FLAG = 0.20        # |cumulative idiosyncratic| at/above 20% is "large"
R2_HIGH = 0.60                    # factors explain >=60% of daily variance is "high"

# Static, always-true caveat about the oil/gas futures proxies (surfaced in the UI + saved to the
# audit trail whenever oil or gas is in the active factor set).
OIL_FACTOR_CAVEAT = (
    "Oil/gas factors use continuous front-month futures (CL=F / NG=F). Monthly contract rolls and a "
    "non-synchronous close (futures settle ~2:30pm ET vs the 4pm equity close) attenuate the fitted "
    "commodity betas, which can push genuine commodity-driven moves into the idiosyncratic (α+ε) "
    "return. Read idiosyncratic strength alongside R² — a large α+ε on a high R² deserves scrutiny."
)

# Surfaced only in `drivers` mode (the Performance-Drivers rich model). In that mode the regression
# nets out market, rates, energy, SECTOR, STYLE and MACRO — so the idiosyncratic (α+ε) return line and
# the Track 1/2/Reject tags mean "own return after removing ALL of those drivers", NOT the commodity-
# adjusted read of 4factor/commodity mode. Idiosyncratic here is therefore smaller and stricter. Use
# 4factor/commodity mode for the "commodity-ride" verdict; use drivers mode for the full risk breakdown.
DRIVERS_MODE_CAVEAT = (
    "Drivers mode removes market, rates, energy, sector, style and macro before measuring the "
    "idiosyncratic (α+ε) return — so the verdict here is stricter than 4factor mode (it strips the sector "
    "and style tides too, not just commodities). For the 'is it only a commodity ride' check, use "
    "4factor or commodity mode; use drivers mode for the full variance breakdown above."
)

# Surfaced only in `boss` mode (WTI + Brent together), which the boss's literal spec requested.
BRENT_COLLINEARITY_CAVEAT = (
    "This run includes BOTH WTI (oil) and Brent — they're ~0.95 correlated, so the model can't cleanly "
    "split oil sensitivity between them: the individual β_oil and β_brent are unstable and can even flip "
    "sign. Read their SUM (the combined oil beta shown below), not each alone. α, R² and the "
    "idiosyncratic return are unaffected (a collinear factor adds no explanatory power)."
)


def combined_oil_beta(reg) -> float | None:
    """Sum of WTI + Brent partial betas — stable even when the two individually are not. None if the
    run isn't using both."""
    b = reg.betas
    if "oil" in b and "brent" in b:
        return float(b["oil"] + b["brent"])
    return None


ALPHA_P = 0.05                    # two-sided significance threshold for "real" alpha
ALPHA_T_TENTATIVE = 1.0           # |t| between this and ~2 (p<0.05) = "not proven"; below = "likely luck"


@dataclass
class TrendVerdict:
    passed: bool
    idio_endpoint: float          # cumulative idiosyncratic (alpha+eps), additive
    raw_endpoint: float           # compounded raw return over the window
    slope_per_day: float          # avg idiosyncratic return per day
    track_tag: str
    verdict_line: str             # one-line plain-language read
    tracking_noise: bool = False  # True => idio may be inflated by factor-tracking noise (see note)
    tracking_noise_note: str = "" # plain-language explanation when flagged (empty otherwise)
    # --- alpha significance & quality (the #3 enhancement: is the own-merit drift REAL?) ----------
    alpha_annualized: float = 0.0
    alpha_tstat: float = 0.0
    alpha_pvalue: float = 1.0
    information_ratio: float = 0.0
    alpha_significant: bool = False
    alpha_verdict: str = ""       # one-line plain read of the significance
    alpha_tier: str = ""          # "Real" | "Not proven" | "Likely luck" (the simple confidence tag)

    @property
    def rank_key(self) -> float:
        """Primary sort: risk-adjusted alpha (information ratio). NaN sinks to the bottom."""
        ir = self.information_ratio
        return ir if ir == ir else float("-inf")


def _alpha_tier(reg) -> str:
    """Simple confidence tag for the own-merit return: 'Real' (statistically solid, ~t≥2 / p<0.05),
    'Not proven' (leaning real, t≥1 but short of significant), or 'Likely luck' (weak or negative)."""
    a = reg.alpha_annualized
    if a > 0 and reg.alpha_significant(ALPHA_P):
        return "Real"
    if a > 0 and abs(reg.alpha_tstat) >= ALPHA_T_TENTATIVE:
        return "Not proven"
    return "Likely luck"


def _alpha_verdict(reg, idio_end: float) -> str:
    """One plain sentence behind the tier tag (no p-values / jargon in the headline)."""
    tier = _alpha_tier(reg)
    a = reg.alpha_annualized
    if tier == "Real":
        return f"Real — the idiosyncratic return is unlikely to be luck (α {a:+.0%}/yr, t {reg.alpha_tstat:+.1f})."
    if tier == "Not proven":
        return (f"Not proven — leaning real but could still be luck "
                f"(α {a:+.0%}/yr, t {reg.alpha_tstat:+.1f}).")
    return f"Likely luck — no dependable idiosyncratic edge (t {reg.alpha_tstat:+.1f})."


def check_trend(result: RegressionResult, deadband: float = 0.02) -> TrendVerdict:
    # Compounding convention throughout the user-facing app (one convention, no confusion).
    idio_end = result.idio_return_compounded()
    raw_end = result.raw_return_compounded()
    slope = idio_end / max(result.n_obs, 1)

    idio_up = idio_end > deadband
    raw_up = raw_end > deadband

    if raw_up and idio_up:
        tag = TRACK_1
    elif idio_up and not raw_up:
        tag = TRACK_2
    elif raw_up and not idio_up:
        tag = REJECT
    else:
        tag = NEUTRAL

    line = (
        f"Price {raw_end:+.0%}, idiosyncratic return {idio_end:+.0%} → "
        + {
            TRACK_1: "rising on its own.",
            TRACK_2: "price is down, but the idiosyncratic return is improving.",
            REJECT: "it only rose by riding its sector / commodity — no idiosyncratic gain.",
            NEUTRAL: "no clear idiosyncratic trend.",
        }[tag]
    )

    tracking_noise = abs(idio_end) >= IDIO_MAGNITUDE_FLAG and result.r2 >= R2_HIGH
    tracking_noise_note = (
        f"Large idiosyncratic ({idio_end:+.0%}) on a high R² ({result.r2:.2f}): the factors already "
        f"explain most daily moves, so part of this α+ε may be factor-tracking noise (CL=F roll / "
        f"non-synchronous close), not a genuine own-story. Corroborate before trusting the trend."
        if tracking_noise else ""
    )

    return TrendVerdict(
        passed=idio_up,
        idio_endpoint=idio_end,
        raw_endpoint=raw_end,
        slope_per_day=slope,
        track_tag=tag,
        verdict_line=line,
        tracking_noise=tracking_noise,
        tracking_noise_note=tracking_noise_note,
        alpha_annualized=result.alpha_annualized,
        alpha_tstat=result.alpha_tstat,
        alpha_pvalue=result.alpha_pvalue,
        information_ratio=result.information_ratio,
        alpha_significant=result.alpha_significant(ALPHA_P),
        alpha_verdict=_alpha_verdict(result, idio_end),
        alpha_tier=_alpha_tier(result),
    )
