"""Gate 3 — AI exposure. Turns an agent GRADE + a human decision into a gate verdict.

SPEC §3/§7 + PLATFORM.md propose-and-approve: the agent (src/agent/exposure_agent.py) grades the AI /
data-center demand story strong|moderate|low|none and sources evidence; the reviewer approves the
grade (or overrides it to their own grade). The FINAL (approved/overridden) grade maps to the gate:
strong/moderate → pass, low → flag, none → fail. Nothing passes without the human's sign-off.
"""
from __future__ import annotations

from dataclasses import dataclass

# Final AI-exposure grade -> gate status + reading.
_GRADE_STATUS = {
    "strong": ("pass", "strong AI/data-center demand — approved"),
    "moderate": ("pass", "moderate AI/data-center demand — approved"),
    "low": ("flag", "low / tangential AI exposure — approved"),
    "none": ("fail", "no AI/data-center exposure — approved"),
}


@dataclass
class ExposureVerdict:
    status: str        # pass | flag | fail | pending | unverified
    type: str
    note: str


def exposure_verdict(grade: str | None, decision: str | None, type_: str = "unknown",
                     error: str | None = None) -> ExposureVerdict:
    """grade: strong|moderate|low|none|'error'|None. decision: 'approved'|'rejected'|None.
    On approval the `grade` is the FINAL grade (the reviewer may have overridden the AI's proposal)."""
    if grade is None:
        return ExposureVerdict("pending", type_, "not run yet")
    if grade == "error":
        return ExposureVerdict("unverified", type_ or "unknown", f"agent error: {error}")
    if decision == "rejected":
        return ExposureVerdict("fail", type_, "rejected by reviewer")
    if decision != "approved":
        return ExposureVerdict("pending", type_, f"proposed grade: {grade} — awaiting approval")
    status, note = _GRADE_STATUS.get(grade, ("unverified", f"unknown grade '{grade}'"))
    return ExposureVerdict(status, type_, note)
