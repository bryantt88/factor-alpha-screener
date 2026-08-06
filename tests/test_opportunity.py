"""Offline correctness tests for the opportunity engine (src/opportunity/engine.py).

Deterministic synthetic inputs (no network) exercise every path: the four buckets, the directional-long
bar, clean-pair construction + matched hedge ratio, the factor-hedged book, and the honest 'no trade'
fallback. Run:  python -m pytest tests/test_opportunity.py -q
"""
from types import SimpleNamespace

from src.opportunity.engine import build_opportunities, OPP_MIN_IR
from src.regression.variance import VarianceDecomposition


def _variance(groups, shares):
    return VarianceDecomposition(shares=shares, r2=sum(v for k, v in shares.items()
                                                        if k != "Idiosyncratic"),
                                 groups=groups)


def _stock(ticker, *, idio, tier, ir, tstat, betas, r2, noisy=False, variance=None):
    reg = SimpleNamespace(betas=betas, r2=r2)
    trend = SimpleNamespace(idio_endpoint=idio, alpha_tier=tier, tracking_noise=noisy,
                            information_ratio=ir, alpha_tstat=tstat, raw_endpoint=idio)
    return SimpleNamespace(ticker=ticker, reg=reg, trend=trend, variance=variance)


def _result(outputs, factor_map):
    config = SimpleNamespace(factor_map=factor_map)
    return SimpleNamespace(outputs=outputs, config=config)


FACTOR_MAP = {"market": "SPY", "rates": "TLT", "oil": "CL=F", "gas": "NG=F"}


def _basket():
    aaa = _stock("AAA", idio=0.20, tier="Real", ir=1.2, tstat=2.6,
                 betas={"market": 1.0, "gas": 0.8}, r2=0.5,
                 variance=_variance({"Market": ["market"], "Energy": ["gas"]},
                                    {"Market": 0.30, "Energy": 0.20, "Idiosyncratic": 0.50}))
    bbb = _stock("BBB", idio=0.15, tier="Likely luck", ir=0.3, tstat=0.7,
                 betas={"market": 0.9, "gas": 0.9}, r2=0.7,
                 variance=_variance({"Market": ["market"], "Energy": ["gas"]},
                                    {"Market": 0.40, "Energy": 0.30, "Idiosyncratic": 0.30}))
    ccc = _stock("CCC", idio=-0.10, tier="Likely luck", ir=-0.5, tstat=-0.4,
                 betas={"market": 1.1}, r2=0.6,
                 variance=_variance({"Market": ["market"]},
                                    {"Market": 0.60, "Idiosyncratic": 0.40}))
    ddd = _stock("DDD", idio=0.0, tier="Likely luck", ir=0.0, tstat=0.0,
                 betas={"market": 0.2}, r2=0.05,
                 variance=_variance({"Market": ["market"]},
                                    {"Market": 0.05, "Idiosyncratic": 0.95}))
    return {"AAA": aaa, "BBB": bbb, "CCC": ccc, "DDD": ddd}


def test_buckets():
    opp = build_opportunities(_result(_basket(), FACTOR_MAP))
    by = {r.ticker: r.bucket for r in opp.reads}
    assert by["AAA"] == "Rising on its own"    # positive gap, Real, not noisy
    assert by["BBB"] == "Just riding factors"  # positive gap but not real -> fade
    assert by["CCC"] == "Lagging its factors"  # negative gap with real factor exposure
    assert by["DDD"] == "No clear edge"        # gap within dead-band


def test_directional_long_bar():
    opp = build_opportunities(_result(_basket(), FACTOR_MAP))
    assert opp.longs == ["AAA"]            # only the Core-long clearing OPP_MIN_IR
    assert opp.none is False


def test_low_ir_core_long_is_not_a_trade():
    b = _basket()
    b["AAA"].trend.information_ratio = OPP_MIN_IR - 0.01   # real alpha but too weak to trade
    opp = build_opportunities(_result(b, FACTOR_MAP))
    assert opp.longs == []
    # still bucketed "Rising on its own" (descriptive), just not a directional trade
    assert next(r.bucket for r in opp.reads if r.ticker == "AAA") == "Rising on its own"


def test_clean_pair_and_hedge_ratio():
    opp = build_opportunities(_result(_basket(), FACTOR_MAP))
    assert len(opp.pairs) == 1
    p = opp.pairs[0]
    assert p.long == "AAA" and p.short == "BBB"
    assert p.factor == "market"                       # the larger shared same-sign exposure
    assert abs(p.hedge_ratio - (1.0 / 0.9)) < 1e-9    # w = beta_L / beta_S neutralises market


def test_factor_hedged_book():
    opp = build_opportunities(_result(_basket(), FACTOR_MAP))
    assert opp.book is not None
    assert [l.ticker for l in opp.book.longs] == ["AAA"]
    hedges = {h.label: (h.ticker, h.weight) for h in opp.book.hedges}
    # single long AAA (weight 1.0): net market beta 1.0 -> short SPY 1.0; net gas 0.8 -> short NG=F 0.8
    assert hedges["market"][0] == "SPY" and abs(hedges["market"][1] + 1.0) < 1e-9
    assert hedges["gas"][0] == "NG=F" and abs(hedges["gas"][1] + 0.8) < 1e-9


def test_no_trade_message_when_nothing_qualifies():
    # a basket with only weak/negative names -> honest "no trade"
    weak = {"CCC": _basket()["CCC"], "DDD": _basket()["DDD"]}
    opp = build_opportunities(_result(weak, FACTOR_MAP))
    assert opp.none is True
    assert opp.longs == [] and opp.pairs == []
    assert "No trade idea meets the bar" in opp.message
