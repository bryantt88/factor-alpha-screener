"""Gate 1 — Size (deterministic, SPEC §3). Pass if market_cap >= size_floor (default $2B)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SizeVerdict:
    passed: bool | None       # None = unverified (market cap unavailable)
    market_cap: float | None
    note: str


def check_size(market_cap: float | None, size_floor: float) -> SizeVerdict:
    if market_cap is None:
        return SizeVerdict(None, None, "market cap unavailable (unverified)")
    passed = market_cap >= size_floor
    return SizeVerdict(passed, market_cap,
                       f"${market_cap/1e9:.1f}B vs ${size_floor/1e9:.0f}B floor")
