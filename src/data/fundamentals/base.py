"""Abstract fundamentals backend interface (docs/DATA.md).

Both backends return the same REQUIRED_FIELDS; missing values are None and flagged `unverified`,
never guessed (CLAUDE.md rule 2). Switching source is a one-line config change.
"""
from __future__ import annotations

REQUIRED_FIELDS = (
    "ebitda_margin", "ebitda_margin_yoy", "net_debt", "ebitda", "net_debt_to_ebitda",
    "last_eps_actual", "last_eps_consensus", "last_rev_actual", "last_rev_consensus",
    "fwd_ev_ebitda", "ev_ebitda_3yr_median",
)


class FundamentalsBackend:
    """Interface every backend implements."""

    def get_fundamentals(self, ticker):
        """Return a dict of REQUIRED_FIELDS (None where unavailable). TODO Step 3."""
        raise NotImplementedError("Step 3")
