"""Run identity / dedup hash (SPEC §8).

    run_id = hash(sorted_tickers + factor_set + return_frequency + time_horizon + as_of_date)

Exact match on all five -> duplicate (same tickers, params, and data date). A different date,
horizon, or factor set is a legitimately new record.
"""
from __future__ import annotations

import hashlib


def compute_run_id(tickers, factor_set, return_frequency, time_horizon, as_of_date) -> str:
    key = "|".join([
        ",".join(sorted(t.upper() for t in tickers)),
        str(factor_set),
        str(return_frequency),
        str(time_horizon),
        str(as_of_date),
    ])
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{as_of_date}_{factor_set}_{digest}"
