"""`edgar` fundamentals backend — SEC EDGAR XBRL company facts (data.sec.gov).

Free, no API key, and PRIMARY-SOURCE: every figure is a value the company actually filed, so it's
credible and auditable. Anything not present is None/`unverified`, never guessed (CLAUDE.md rule 2).

Kept CURRENT to the latest filing: SEC's aggregated `companyfacts` feed lags a freshly filed 10-Q/10-K
by days-to-weeks (right through earnings season it can sit a full quarter behind a report that's already
public). So `_facts` starts from that feed and then merges the XBRL of any 10-Q/10-K whose period is
newer than the feed contains — read straight from the filed document. The result is as fresh as EDGAR
itself while staying primary-source; the extra fetch only fires when a newer filing actually exists.

FLOW items (revenue, operating income, D&A -> EBITDA) are reported on a **TTM (trailing-twelve-month)**
basis by default — more decision-relevant than the last fiscal year, and the basis a PM sees on a
screener. TTM is reconstructed from filed quarters: each discrete quarter is recovered by differencing
consecutive year-to-date figures within a fiscal year (Q1=3mo, Q2=6mo-3mo, Q3=9mo-6mo, Q4=FY-9mo), then
the trailing four are summed. When four contiguous quarters can't be formed, the field falls back to the
latest full fiscal year, and the basis is labelled per ticker (`TTM->end` vs `FYxxxx`). Balance-sheet
items (debt, cash) use the latest reported instant.

EBITDA prefers `OperatingIncomeLoss + D&A`. When a filer has stopped tagging operating income (e.g.
Eaton retired `OperatingIncomeLoss` ~2019), it falls back to a BOTTOM-UP `pretax income + interest
expense + D&A` — the same construction Yahoo uses — labelled `(EBIT+D&A)` in the basis so it's
transparently a derived figure, not a filed operating-income line.

Net debt = interest-bearing debt + FINANCE (capital) leases - cash, at the latest fresh instant, summed
from the concepts a filer actually uses (long-term debt +/- its current portion, commercial paper /
other short-term borrowings, and finance-lease liabilities), with per-component freshness so a retired
tag can't slip a years-old figure into the total. Operating leases are excluded (standard net-debt
convention); on the handful of names where Yahoo bundles operating-lease liabilities into its headline
debt, ours reads a little lower by exactly that amount — deliberate and auditable, never fabricated.

Two guards keep numbers honest: concept synonyms are tried in PRIORITY ORDER (the clean canonical tag
first — ties never fall through to a messier tag), and any figure whose latest period is older than
`STALE_AFTER_DAYS` is dropped to `unverified` rather than reported stale (companies switch/retire XBRL
tags, which would otherwise surface a years-old figure as if current).

Two fields EDGAR does not carry are augmented from yfinance and labelled as such:
  - analyst CONSENSUS EPS (a data-vendor product, not in filings) — paired with the reported EPS from
    the same yfinance endpoint so the surprise is internally consistent;
  - live MARKET CAP, only to turn filed net-debt + EBITDA into a current trailing EV/EBITDA.

US filers only (foreign 20-F filers -> the fields stay unverified, honestly).
"""
from __future__ import annotations

import datetime as _dt
import xml.etree.ElementTree as _ET
from collections import defaultdict

from .base import REQUIRED_FIELDS, FundamentalsBackend

_UA = {"User-Agent": "Factor-Alpha-Screener (contact: bryant.effendi@xpef.org)"}
_CIK_MAP: dict | None = None
_FACTS_CACHE: dict = {}          # cik -> merged facts (per process; avoids refetch across gates)
_SUBMISSIONS_CACHE: dict = {}    # cik -> submissions index (per process)
_XBRLI = "http://www.xbrl.org/2003/instance"
_XSI = "http://www.w3.org/2001/XMLSchema-instance"

# Concept synonyms in PRIORITY ORDER (clean canonical tag first). Companies switch tags over time.
# `Revenues` (income-statement TOTAL) first so the margin denominator matches the base operating
# income is netted from; the ASC-606 contract subset can be materially smaller for filers with large
# non-customer revenue (e.g. CEG's derivative mark-to-market). Stale totals (e.g. NEE's `Revenues`
# stops 2012) are excluded by the recency rule, so ordering only decides genuine ties.
# Our high-priority tags come FIRST (they make us tie to Yahoo — e.g. `Revenues` total before the
# ASC-606 contract subset); broader industry fallbacks (banks, oil & gas, services, tag-switchers) are
# APPENDED at lower priority so they only fire when the preferred tags have no recent data. `_best_*`
# picks the synonym with the most-recent coverage, ties → earlier synonym, so appending is safe.
_REV_SYNS = (
    "Revenues", "RegulatedAndUnregulatedOperatingRevenue",
    "RevenueFromContractWithCustomerExcludingAssessedTax", "RevenueFromContractWithCustomerIncludingAssessedTax",
    "SalesRevenueNet", "SalesRevenueGoodsNet",
    "SalesRevenueServicesNet", "RevenuesNetOfInterestExpense", "InterestAndDividendIncomeOperating",
    "SalesRevenueServicesGross", "OilAndGasRevenue", "ContractsRevenue",
)
_DA_SYNS = (
    "DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
    "DepreciationAndAmortization", "DepreciationDepletionAndAmortizationExcludingNuclearFuel",
    # Oil & gas full-cost / successful-efforts DD&A (complete-measure concepts only — partial-measure
    # tags like the COGS-embedded D&A are deliberately excluded so we never understate the add-back).
    "ResultsOfOperationsDepreciationDepletionAmortizationAndAccretion",
    "ResultsOfOperationsDepreciationDepletionAndAmortizationAndValuationProvisions",
)
# Bottom-up EBITDA (EBIT + D&A) when operating income isn't tagged: EBIT = pretax income + interest.
_PRETAX_SYNS = (
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
    "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
)
_INT_SYNS = (
    "InterestExpenseNonoperating", "InterestAndDebtExpense", "InterestExpense", "InterestExpenseDebt",
    "InterestExpenseBorrowings", "InterestExpenseDebtExcludingAmortization", "InterestExpenseOperating",
    "InterestCostsIncurred", "InterestPaidNet", "InterestPaid",   # last two: cash-flow-stmt interest paid
)
# Net income ATTRIBUTABLE TO PARENT: NetIncomeLoss is already parent-only (do NOT subtract NCI);
# ProfitLoss (consolidated incl. NCI) is the fallback for filers that retired NetIncomeLoss (e.g. BE
# switched ~2022). First-that-exists-most-recent wins via _best_annual / _quarter_map.
_NI_SYNS = ("NetIncomeLoss", "ProfitLoss")
STALE_AFTER_DAYS = 550   # ~18 months: a still-current annual has buffer; a retired-tag figure is caught


def _session():
    import requests
    s = requests.Session()
    s.headers.update(_UA)
    return s


def _cik_map(s) -> dict:
    """ticker -> zero-padded CIK, from SEC's master list (cached for the process)."""
    global _CIK_MAP
    if _CIK_MAP is None:
        r = s.get("https://www.sec.gov/files/company_tickers.json", timeout=20)
        r.raise_for_status()
        _CIK_MAP = {row["ticker"].upper(): int(row["cik_str"]) for row in r.json().values()}
    return _CIK_MAP


def _ticker_operating_cik(s, ticker: str) -> int | None:
    """CIK of the entity that actually FILES 10-Ks for a ticker, via EDGAR's company search.
    `company_tickers.json` can point a ticker at a brand-new holding company or shell after a
    reorganisation (e.g. XOM -> 'ExxonMobil Holdings Corp', which has no financials) while the
    10-K/10-Q filer keeps a different CIK. Restricting the search to `type=10-K` returns the
    operating filer. Returns None if the lookup fails."""
    import urllib.parse
    params = urllib.parse.urlencode({"action": "getcompany", "CIK": ticker.upper(),
                                     "type": "10-K", "owner": "include", "count": "10", "output": "atom"})
    try:
        xml = s.get(f"https://www.sec.gov/cgi-bin/browse-edgar?{params}", timeout=30).text
        root = _ET.fromstring(xml.encode("iso-8859-1", errors="replace"))
    except Exception:
        return None
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] == "cik" and el.text and el.text.strip().isdigit():
            return int(el.text.strip())
    return None


def _companyfacts(s, cik: int) -> dict:
    r = s.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json", timeout=30)
    if r.status_code == 404:
        return {}                                  # holdco/shell with no XBRL facts -> caller falls back
    r.raise_for_status()
    return r.json().get("facts", {})


def _submissions(s, cik: int) -> dict:
    """The `submissions` index (recent filings), cached per process. Updates the moment a filing hits
    EDGAR, unlike the aggregated companyfacts/frames feeds (which lag by days-to-weeks)."""
    if cik not in _SUBMISSIONS_CACHE:
        r = s.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", timeout=30)
        r.raise_for_status()
        _SUBMISSIONS_CACHE[cik] = r.json()
    return _SUBMISSIONS_CACHE[cik]


def _recent_filings(s, cik: int) -> list:
    """(form, filed_date, period_end, accession) for 10-Q/10-K, newest filing first."""
    rec = _submissions(s, cik).get("filings", {}).get("recent", {})
    rows = [(fm, fd, rd, ac) for fm, fd, rd, ac in zip(
        rec.get("form", []), rec.get("filingDate", []), rec.get("reportDate", []), rec.get("accessionNumber", []))
        if fm in ("10-Q", "10-K")]
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows


def _instance_facts(s, cik: int, accession: str, form: str, filed: str) -> dict:
    """Parse ONE filing's XBRL instance into {concept: [fact,...]} shaped like companyfacts' USD lists
    (duration facts carry start/end/fy; instants carry end). Only us-gaap USD facts in NON-dimensional
    (consolidated, no segment/member) contexts are kept, so we read the same reported totals the
    aggregated feed would eventually publish — just straight from the filed document."""
    accn = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn}"
    items = s.get(f"{base}/index.json", timeout=30).json().get("directory", {}).get("item", [])
    names = [d["name"] for d in items]
    inst = next((n for n in names if n.endswith("_htm.xml")), None) or next(
        (n for n in names if n.endswith(".xml") and n != "FilingSummary.xml"
         and not n.endswith(("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml"))), None)
    if inst is None:
        return {}
    root = _ET.fromstring(s.get(f"{base}/{inst}", timeout=60).content)

    ctx: dict = {}                              # context id -> ('i', end) | ('d', start, end)
    for c in root.findall(f"{{{_XBRLI}}}context"):
        ent = c.find(f"{{{_XBRLI}}}entity")
        if ent is not None and ent.find(f"{{{_XBRLI}}}segment") is not None:
            continue                            # dimensional breakdown -> not the consolidated total
        per = c.find(f"{{{_XBRLI}}}period")
        if per is None:
            continue
        i = per.find(f"{{{_XBRLI}}}instant")
        if i is not None:
            ctx[c.get("id")] = ("i", i.text)
        else:
            sd, ed = per.find(f"{{{_XBRLI}}}startDate"), per.find(f"{{{_XBRLI}}}endDate")
            if sd is not None and ed is not None:
                ctx[c.get("id")] = ("d", sd.text, ed.text)

    usd = {u.get("id") for u in root.findall(f"{{{_XBRLI}}}unit")                # plain USD units only
           if u.find(f"{{{_XBRLI}}}divide") is None
           and [m.text for m in u.iter(f"{{{_XBRLI}}}measure")][-1:] == ["iso4217:USD"]}

    out: dict = defaultdict(list)
    for el in root.iter():
        cref = el.get("contextRef")
        if not cref or cref not in ctx or el.get("unitRef") not in usd:
            continue
        if el.get(f"{{{_XSI}}}nil") == "true" or not (el.text and el.text.strip()):
            continue
        if not el.tag.startswith("{http://fasb.org/us-gaap"):
            continue
        try:
            val = float(el.text.strip())
        except ValueError:
            continue
        c = ctx[cref]
        concept = el.tag.split("}", 1)[1]
        if c[0] == "d":
            out[concept].append({"start": c[1], "end": c[2], "val": val,
                                 "form": form, "filed": filed, "fy": int(c[2][:4])})
        else:
            out[concept].append({"end": c[1], "val": val, "form": form, "filed": filed})
    return out


def _facts(s, cik: int) -> dict:
    """Company facts, kept CURRENT to the latest filed 10-Q/10-K. Start from the aggregated
    companyfacts feed, then — because that feed lags a freshly filed report by days-to-weeks — merge in
    the XBRL of any 10-Q/10-K whose period is newer than anything the feed contains. The extra fetch
    happens ONLY when a newer filing exists (in-season); otherwise this is a no-op. Cached per process."""
    if cik in _FACTS_CACHE:
        return _FACTS_CACHE[cik]
    facts = _companyfacts(s, cik)
    try:
        gaap = facts.setdefault("us-gaap", {})
        have = max((e.get("end", "") for node in gaap.values()
                    for e in node.get("units", {}).get("USD", [])), default="")
        merged = 0
        for form, fd, rd, acc in _recent_filings(s, cik):
            if rd <= have or merged >= 4:        # sorted newest-first; stop once caught up (bounded)
                break
            for concept, lst in _instance_facts(s, cik, acc, form, fd).items():
                gaap.setdefault(concept, {"units": {"USD": []}})["units"].setdefault("USD", []).extend(lst)
            merged += 1
    except Exception:
        pass                                     # any hiccup -> fall back to the companyfacts feed alone
    _FACTS_CACHE[cik] = facts
    return facts


def _usd(facts: dict, *names: str) -> list:
    """First matching concept's USD fact list (tries tag synonyms in order)."""
    for n in names:
        try:
            return facts["us-gaap"][n]["units"]["USD"]
        except (KeyError, TypeError):
            continue
    return []


# --------------------------------------------------------------------------------------------------
# Flow items -> TTM (reconstructed from filed quarters)
# --------------------------------------------------------------------------------------------------
def _duration_single(facts: dict, name: str) -> list:
    """A single concept's 10-K/10-Q duration facts, deduped by (start,end) with the latest filing
    winning; each carries parsed start/end dates and the period length in days."""
    seen: dict = {}
    try:
        raw = facts["us-gaap"][name]["units"]["USD"]
    except (KeyError, TypeError):
        return []
    for e in raw:
        if not e.get("start") or not e.get("end"):
            continue
        if not str(e.get("form", "")).startswith(("10-K", "10-Q")):
            continue
        try:
            d0 = _dt.date.fromisoformat(e["start"])
            d1 = _dt.date.fromisoformat(e["end"])
        except Exception:
            continue
        key = (d0, d1)
        prev = seen.get(key)
        if prev is None or str(e.get("filed", "")) > prev["filed"]:
            seen[key] = {"start": d0, "end": d1, "days": (d1 - d0).days,
                         "val": float(e["val"]), "filed": str(e.get("filed", ""))}
    return list(seen.values())


def _best_duration(facts: dict, *names: str) -> list:
    """Duration facts for the synonym with the most-recent coverage; on a tie prefer the EARLIER
    synonym (the priority-ordered list puts the clean canonical concept first)."""
    best, best_max = [], None
    for n in names:
        d = _duration_single(facts, n)
        if not d:
            continue
        mx = max(x["end"] for x in d)
        if best_max is None or mx > best_max:      # strictly-more-recent only -> ties keep earlier synonym
            best, best_max = d, mx
    return best


def _quarter_map(dfacts: list) -> dict:
    """end_date -> discrete-quarter value. Each quarter is recovered by differencing consecutive
    cumulative (YTD) facts sharing a fiscal-year start: Q1=3mo, Q2=6mo-3mo, Q3=9mo-6mo, Q4=FY-9mo.
    Explicitly-filed discrete (~90d) facts fall out of the same logic (a start-group of one)."""
    by_start = defaultdict(list)
    for x in dfacts:
        by_start[x["start"]].append(x)
    q: dict = {}
    for group in by_start.values():
        group.sort(key=lambda z: z["end"])
        prev_end, prev_val = None, 0.0
        for x in group:
            span = x["days"] if prev_end is None else (x["end"] - prev_end).days
            if 80 <= span <= 100:                  # this increment is ~one quarter -> a discrete quarter
                q[x["end"]] = x["val"] - prev_val
            prev_end, prev_val = x["end"], x["val"]
    return q


def _ttm(qmap: dict, end):
    """Sum of the 4 contiguous quarters ending at `end`; None if they aren't all present/contiguous."""
    if end not in qmap:
        return None
    ends = sorted(qmap)
    idx = ends.index(end)
    if idx < 3:
        return None
    chosen = ends[idx - 3:idx + 1]
    for a, b in zip(chosen, chosen[1:]):
        if not (80 <= (b - a).days <= 100):        # a gap -> not a clean trailing year
            return None
    return sum(qmap[e] for e in chosen)


def _da_quarter_map(facts: dict) -> dict:
    """D&A discrete quarters — a combined concept if present, else Depreciation + intangible amort
    (intersection of ends, so a partial series never silently understates a quarter)."""
    da_facts = _best_duration(facts, *_DA_SYNS)
    if da_facts:
        return _quarter_map(da_facts)
    dep = _quarter_map(_best_duration(facts, "Depreciation"))
    amo = _quarter_map(_best_duration(facts, "AmortizationOfIntangibleAssets"))
    if dep:                                    # depreciation defines the quarter grid; amort adds on
        return {e: dep[e] + amo.get(e, 0.0) for e in dep}
    return amo


def _flow_ttm(facts: dict):
    """(now, prev, source): the latest TTM (end, rev, ebitda) triple where EBITDA and D&A form a clean
    trailing-twelve-month sum on one common basis, plus the year-earlier triple for the YoY margin.

    `source` is 'op' when EBITDA = operating income + D&A, or 'ebit' when the filer no longer tags
    operating income and EBITDA falls back to bottom-up pretax + interest + D&A. Returns
    (None, None, None) if neither can be formed. `rev` may be None (EBITDA still reported, margin isn't).
    """
    rev_q = _quarter_map(_best_duration(facts, *_REV_SYNS))
    op_q = _quarter_map(_best_duration(facts, "OperatingIncomeLoss"))
    da_q = _da_quarter_map(facts)
    pti_q = _quarter_map(_best_duration(facts, *_PRETAX_SYNS))
    int_q = _quarter_map(_best_duration(facts, *_INT_SYNS))

    def ebit(end, source):
        if source == "op":
            return _ttm(op_q, end)
        p, i = _ttm(pti_q, end), _ttm(int_q, end)
        return None if (p is None or i is None) else p + i

    for source in ("op", "ebit"):          # prefer real operating income; bottom-up only if it's gone
        base = set(op_q) if source == "op" else (set(pti_q) & set(int_q))
        triples = []
        for e in sorted(base & set(da_q)):
            d, eb = _ttm(da_q, e), ebit(e, source)
            if d is not None and eb is not None:
                triples.append((e, _ttm(rev_q, e), eb + d))
        if not triples:
            continue
        now = triples[-1]
        prev = next((t for t in triples if 350 <= (now[0] - t[0]).days <= 380), None)  # ~1yr earlier
        return now, prev, source
    return None, None, None


def _annual_by_fy(entries: list) -> dict:
    """{fiscal_year: (value, end_date)} for ~annual (10-K, ~365-day) flow facts — latest filing wins."""
    out, best_end = {}, {}
    for e in entries:
        if not e.get("start") or not str(e.get("form", "")).startswith("10-K"):
            continue
        try:
            d0 = _dt.date.fromisoformat(e["start"])
            d1 = _dt.date.fromisoformat(e["end"])
        except Exception:
            continue
        if not (350 <= (d1 - d0).days <= 385):
            continue
        fy = e.get("fy")
        if fy is None:
            continue
        if fy not in best_end or e["end"] > best_end[fy]:
            best_end[fy], out[fy] = e["end"], (float(e["val"]), d1)
    return out


def _best_annual(facts: dict, *names: str) -> dict:
    """{fy: (value, end)} from the synonym with the most-recent annual data; on a tie prefer the
    EARLIER synonym (priority order). Companies switch tags, so first-that-exists would grab a
    stale, discontinued series."""
    best: dict = {}
    for n in names:
        d = _annual_by_fy(_usd(facts, n))
        if d and (not best or max(d) > max(best)):     # strictly-more-recent only -> ties keep earlier synonym
            best = d
    return best


def _latest_instant(entries: list):
    """(value, end_date) for the latest point-in-time (balance-sheet) fact, or None. Instant facts
    carry `end` but no `start`."""
    inst = [e for e in entries if not e.get("start")]
    if not inst:
        return None
    inst.sort(key=lambda e: e["end"])
    last = inst[-1]
    try:
        return float(last["val"]), _dt.date.fromisoformat(last["end"])
    except Exception:
        return None


def _net_debt(facts: dict, fresh) -> tuple | None:
    """Latest-instant net debt = interest-bearing debt + finance (capital) leases - cash, summed from
    whichever concepts a filer actually uses. Returns (net_debt, bs_end) or None if debt or cash can't
    be resolved. Every component is freshness-guarded individually, so a retired tag (e.g. Eaton's
    2014-vintage `LongTermDebtNoncurrent`) is dropped rather than blended with fresh short-term debt.
    Operating leases are excluded (standard net-debt convention)."""

    def inst(*names):
        """Latest FRESH instant among the synonyms, as (value, end, matched_name), or None."""
        for n in names:
            r = _latest_instant(_usd(facts, n))
            if r and fresh(r[1]):
                return r[0], r[1], n
        return None

    leases_in_debt = False
    # --- long-term debt (+ current maturities) ---
    lt = inst("LongTermDebtNoncurrent")
    if lt:                                          # noncurrent tag -> add the current portion separately
        debt, end = lt[0], lt[1]
        cur = inst("LongTermDebtCurrent")
        if cur:
            debt += cur[0]; end = max(end, cur[1])
    else:                                           # else a total-debt concept (already includes current)
        tot = inst("LongTermDebt",
                   "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
                   "LongTermDebtAndCapitalLeaseObligations", "DebtAndCapitalLeaseObligations",
                   "DebtLongtermAndShorttermCombinedAmount", "NotesAndLoansPayable", "NotesPayable")
        if not tot:
            return None
        debt, end = tot[0], tot[1]
        if "CapitalLeaseObligations" in tot[2]:
            leases_in_debt = True                   # this concept already bundles finance leases
        if tot[2] == "LongTermDebtAndCapitalLeaseObligations":   # noncurrent-only -> add current portion
            cur = inst("LongTermDebtAndCapitalLeaseObligationsCurrent")
            if cur:
                debt += cur[0]; end = max(end, cur[1])

    # --- short-term / other borrowings: the umbrella tag if fresh, else its components ---
    st = inst("ShortTermBorrowings", "ShortTermDebt", "NotesAndLoansPayableCurrent",
              "LinesOfCreditCurrent", "LoansPayableCurrent")
    if st:
        debt += st[0]; end = max(end, st[1])
    else:
        for c in (inst("CommercialPaper"), inst("OtherShortTermBorrowings")):
            if c:
                debt += c[0]; end = max(end, c[1])

    # --- finance (capital) leases, unless the debt concept above already includes them ---
    if not leases_in_debt:
        fl = inst("FinanceLeaseLiability")
        if fl is None:
            s, e = 0.0, None
            for c in (inst("FinanceLeaseLiabilityCurrent"), inst("FinanceLeaseLiabilityNoncurrent")):
                if c:
                    s += c[0]; e = c[1] if e is None else max(e, c[1])
            fl = (s, e, "split") if e is not None else None
        if fl:
            debt += fl[0]; end = max(end, fl[1])

    # --- cash: cash-and-equivalents; else the restricted-inclusive total, net of restricted cash ---
    cash = inst("CashAndCashEquivalentsAtCarryingValue",
                "CashAndCashEquivalentsAtCarryingValueIncludingDiscontinuedOperations", "Cash")
    if cash is None:
        cc = inst("CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents")
        if cc:
            rc = inst("RestrictedCash", "RestrictedCashAndCashEquivalentsAtCarryingValue")
            cash = (cc[0] - (rc[0] if rc else 0.0), cc[1], "unrestricted")
    if cash is None:
        return None
    # Short-term (current) marketable securities are cash-like and netted against debt (Yahoo does the
    # same); this closes the net-debt gap on cash-rich names (e.g. Apple's ~$23B). LONG-term investments
    # are deliberately excluded — they aren't "cash". Utilities/generators tag ~none, so this is a no-op
    # for the power-stack universe.
    sti = inst("ShortTermInvestments", "MarketableSecuritiesCurrent", "OtherShortTermInvestments")
    total_cash = cash[0] + (sti[0] if sti else 0.0)
    return debt - total_cash, max(end, cash[1], sti[1] if sti else cash[1])


class EdgarFundamentals(FundamentalsBackend):
    def get_fundamentals(self, ticker: str) -> dict:
        vals = {k: None for k in REQUIRED_FIELDS}
        basis = self._from_edgar(ticker, vals)       # filed financials; failures -> unverified
        self._eps_pair_from_yfinance(ticker, vals)   # consensus EPS (not in filings)
        unverified = {k for k in REQUIRED_FIELDS if vals[k] is None}
        from ..industry import benchmark_for         # Damodaran industry averages (real, sourced)
        return {"values": vals, "unverified": unverified, "basis": basis,
                "industry": benchmark_for(ticker)}

    def _from_edgar(self, ticker: str, vals: dict) -> str | None:
        """Populate flow + balance-sheet fields; return the flow basis label ('TTM->..' / 'FYxxxx')."""
        try:
            s = _session()
            cik = _cik_map(s).get(ticker.upper())
            if cik is None:
                cik = _ticker_operating_cik(s, ticker)      # not in the master list -> search EDGAR
            elif not _recent_filings(s, cik):               # mapped to a shell/holdco with no 10-K/10-Q
                cik = _ticker_operating_cik(s, ticker) or cik
            if cik is None:
                return None
            f = _facts(s, cik)
            today = _dt.date.today()

            def fresh(end) -> bool:
                return end is not None and (today - end).days <= STALE_AFTER_DAYS

            # --- flow items: TTM first, else latest full fiscal year (both freshness-guarded) ---
            # EBITDA suffix ' (EBIT+D&A)' marks a bottom-up (pretax+interest+D&A) figure for filers
            # that no longer tag operating income, so the basis stays transparent.
            basis, rev, ebitda = None, None, None
            now, prev, source = _flow_ttm(f)
            if now and fresh(now[0]):
                end, rev, ebitda = now
                basis = f"TTM->{end.isoformat()}" + ("" if source == "op" else " (EBIT+D&A)")
                if prev and prev[1] and rev:         # YoY = current TTM margin - year-earlier TTM margin
                    vals["ebitda_margin_yoy"] = ebitda / rev - prev[2] / prev[1]
                # net income (same TTM quarters) + revenue/net-income YoY trend (P/E computed later)
                ni_q = _quarter_map(_best_duration(f, *_NI_SYNS))
                ni_now = _ttm(ni_q, end)
                if ni_now is not None:
                    vals["net_income"] = ni_now
                if prev:
                    if prev[1] and rev:
                        vals["revenue_yoy"] = (rev - prev[1]) / prev[1]
                    ni_prev = _ttm(ni_q, prev[0])
                    if ni_now is not None and ni_prev not in (None, 0):
                        vals["net_income_yoy"] = (ni_now - ni_prev) / abs(ni_prev)
            else:
                rev_a = _best_annual(f, *_REV_SYNS)
                da_a = _best_annual(f, *_DA_SYNS)
                if not da_a:
                    dep, amo = _best_annual(f, "Depreciation"), _best_annual(f, "AmortizationOfIntangibleAssets")
                    da_a = {fy: (dep.get(fy, (0.0,))[0] + amo.get(fy, (0.0,))[0],
                                 max((dep.get(fy) or (0.0, None))[1], (amo.get(fy) or (0.0, None))[1]))
                            for fy in (set(dep) | set(amo))
                            if fy in dep or fy in amo}
                # EBITDA by fiscal year from operating income + D&A, else bottom-up (pretax+interest)
                # + D&A. Prefer operating income, but only if its latest FY is still fresh — a filer
                # that retired `OperatingIncomeLoss` years ago (Eaton) has stale op data, so fall through.
                def _annual_eb(src):
                    if src == "op":
                        e = _best_annual(f, "OperatingIncomeLoss")
                    else:
                        pti_a, int_a = _best_annual(f, *_PRETAX_SYNS), _best_annual(f, *_INT_SYNS)
                        e = {fy: (pti_a[fy][0] + int_a[fy][0], max(pti_a[fy][1], int_a[fy][1]))
                             for fy in (set(pti_a) & set(int_a))}
                    return {fy: (e[fy][0] + da_a[fy][0], max(e[fy][1], da_a[fy][1]))
                            for fy in e if fy in da_a}

                src, eb_fy = None, {}
                for cand_src in ("op", "ebit"):
                    cand = _annual_eb(cand_src)
                    if cand and fresh(cand[max(cand)][1]):
                        src, eb_fy = cand_src, cand
                        break
                if eb_fy:
                    ly = max(eb_fy)
                    eb_val, eb_end = eb_fy[ly]
                    if fresh(eb_end):
                        ebitda = eb_val
                        basis = f"FY{ly}" + ("" if src == "op" else " (EBIT+D&A)")
                        if ly in rev_a and rev_a[ly][0]:
                            rev = rev_a[ly][0]
                            prev_fy = ly - 1
                            m_now = eb_val / rev
                            if prev_fy in eb_fy and prev_fy in rev_a and rev_a[prev_fy][0]:
                                m_prev = eb_fy[prev_fy][0] / rev_a[prev_fy][0]
                                vals["ebitda_margin_yoy"] = m_now - m_prev
                            if prev_fy in rev_a and rev_a[prev_fy][0]:
                                vals["revenue_yoy"] = (rev - rev_a[prev_fy][0]) / rev_a[prev_fy][0]

            # net income (annual fallback if the TTM path didn't produce one) + YoY
            if vals.get("net_income") is None:
                ni_a = _best_annual(f, *_NI_SYNS)
                if ni_a:
                    ly_ni = max(ni_a)
                    v_ni, e_ni = ni_a[ly_ni]
                    if fresh(e_ni):
                        vals["net_income"] = v_ni
                        pf = ly_ni - 1
                        if vals.get("net_income_yoy") is None and pf in ni_a and ni_a[pf][0]:
                            vals["net_income_yoy"] = (v_ni - ni_a[pf][0]) / abs(ni_a[pf][0])

            if ebitda is not None:
                vals["ebitda"] = ebitda
                if rev:
                    vals["ebitda_margin"] = ebitda / rev
                    vals["last_rev_actual"] = rev

            # --- live market cap (fetched once) → P/E and trailing EV/EBITDA ---
            from ..market_cap import get_market_cap
            mc = get_market_cap(ticker)
            ni = vals.get("net_income")
            if mc and ni and ni > 0:                      # P/E only meaningful on positive earnings
                vals["pe_ratio"] = mc / ni

            # --- balance sheet: net debt at the latest fresh instant (see _net_debt) ---
            nd = _net_debt(f, fresh)
            if nd is not None:
                net_debt, bs_end = nd
                if fresh(bs_end):
                    vals["net_debt"] = net_debt
                    if ebitda:
                        vals["net_debt_to_ebitda"] = net_debt / ebitda
                        if mc:                            # trailing EV/EBITDA on LIVE mkt cap
                            vals["fwd_ev_ebitda"] = (mc + net_debt) / ebitda
            return basis
        except Exception:
            return None   # network / parse / tag-mismatch -> leave the fields unverified, never fabricate

    def _eps_pair_from_yfinance(self, ticker: str, vals: dict) -> None:
        """Reported + consensus EPS for the last quarter (paired, so the surprise is consistent)."""
        try:
            import math

            import yfinance as yf
            df = yf.Ticker(ticker).get_earnings_dates(limit=8)
            past = df[df["Reported EPS"].notna()]
            if len(past):
                row = past.iloc[0]
                for field, col in (("last_eps_actual", "Reported EPS"), ("last_eps_consensus", "EPS Estimate")):
                    v = row.get(col)
                    try:
                        v = float(v)
                        vals[field] = None if math.isnan(v) else v
                    except (TypeError, ValueError):
                        vals[field] = None
        except Exception:
            pass
