"""Regression tests locking two audit fixes (2026-08-09 full recheck; no network).

1. EDGAR net-debt: a combined long+short total-debt concept must NOT be double-counted with a
   separate short-term-borrowings tag, while the common LongTermDebt(+ST) path must be unaffected.
2. Gate-2 leverage: a negative net-debt/EBITDA ratio caused by NON-POSITIVE EBITDA is undefined
   leverage (-> unverified), never a "pass"; but genuine net cash (negative net debt over positive
   EBITDA) must still pass.
"""
import datetime as _dt

from src.data.fundamentals.edgar import _net_debt
from src.gates.fundamentals import check_fundamentals, HARD_METRICS

_END = _dt.date(2026, 3, 31)


def _fresh(d):
    return (_dt.date(2026, 8, 9) - d).days <= 550


def _facts(**concepts):
    return {"us-gaap": {n: {"units": {"USD": [{"end": _END.isoformat(), "val": v}]}}
                        for n, v in concepts.items()}}


def test_net_debt_no_short_term_double_count():
    # combined LT+ST total already includes short-term -> ST tag must not be added again
    nd, _ = _net_debt(_facts(DebtLongtermAndShorttermCombinedAmount=1000, ShortTermBorrowings=200,
                             CashAndCashEquivalentsAtCarryingValue=100), _fresh)
    assert nd == 900.0
    # NotesAndLoansPayable total vs its current portion -> no double-count
    nd, _ = _net_debt(_facts(NotesAndLoansPayable=1000, NotesAndLoansPayableCurrent=200,
                             CashAndCashEquivalentsAtCarryingValue=100), _fresh)
    assert nd == 900.0


def test_net_debt_short_term_still_added_on_long_term_paths():
    # LongTermDebt is LT (incl. current maturities of LTD), NOT short-term borrowings -> ST still added
    nd, _ = _net_debt(_facts(LongTermDebt=1000, ShortTermBorrowings=200,
                             CashAndCashEquivalentsAtCarryingValue=100), _fresh)
    assert nd == 1100.0
    # the common noncurrent path (CEG/NEE/etc.) is unchanged
    nd, _ = _net_debt(_facts(LongTermDebtNoncurrent=1000, LongTermDebtCurrent=50,
                             ShortTermBorrowings=200, CashAndCashEquivalentsAtCarryingValue=100), _fresh)
    assert nd == 1150.0


def _leverage_status(nde, margin):
    vals = {k: None for k in (
        "ebitda_margin", "ebitda_margin_yoy", "net_debt_to_ebitda",
        "last_eps_actual", "last_eps_consensus", "fwd_ev_ebitda", "ev_ebitda_3yr_median")}
    vals["net_debt_to_ebitda"] = nde
    vals["ebitda_margin"] = margin
    return check_fundamentals({"values": vals}, 6.0).metrics["net_debt_to_ebitda"].status


def test_negative_ebitda_leverage_is_unverified_not_pass():
    assert _leverage_status(-3.0, -0.05) == "unverified"   # loss-maker: leverage undefined


def test_net_cash_still_passes_leverage():
    assert _leverage_status(-1.5, 0.20) == "pass"          # genuine net cash
    assert _leverage_status(3.0, 0.20) == "pass"
    assert _leverage_status(9.0, 0.20) == "fail"


def test_missing_values_never_crashes_a_ticker():
    # scorecard-not-funnel: an absent key surfaces 'unverified', never a KeyError crash
    assert check_fundamentals({"values": {}}, 6.0).overall == "unverified"
    assert check_fundamentals({}, 6.0).overall == "unverified"
    assert set(HARD_METRICS) <= set(check_fundamentals({}, 6.0).metrics)
