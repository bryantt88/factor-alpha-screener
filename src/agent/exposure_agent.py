"""AI-exposure agent (SPEC §7) — Gate 3, the ONLY LLM decision in the system.

The agent grades a company's OVERALL AI / data-center demand story as strong | moderate | low | none
and proposes sourced evidence bullets. A human approves or overrides the grade before it counts
(propose-and-approve). Two retrieval modes:
  - 'news'  (quick, ~25s): grounded in the ticker's recent yfinance news (real URLs); bullets may cite
            ONLY those provided URLs (enforced in code, so a fabricated link can't survive). The GRADE
            may also use the model's general knowledge of the business (the grade is qualitative text,
            not a number — hard rule 1 forbids fabricated NUMBERS, not a qualitative read).
  - 'web'   (deep, ~2min): the model uses live web search (gemini `-y`) to find recent AI/data-center
            demand signals and returns the source URLs it found. No provided allowlist exists, so those
            links are shown as 'web-sourced — verify before approving' (the human verifies on approval).
Guardrails (CLAUDE.md rule 1): no financial numbers ever; under-claim rather than fabricate.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .gemini_client import GeminiError, call_gemini

TYPES = ["merchant_gas", "nuclear", "regulated", "renewable", "geothermal", "equipment"]
GRADES = ["strong", "moderate", "low", "none"]

_RULES = (
    "You are a buy-side analyst assessing a company's AI / data-center demand exposure for a portfolio "
    "manager. Return ONLY a JSON object (no prose, no code fences).\n"
    "Grade the OVERALL strength of the company's AI / data-center demand story as exactly one of: "
    "strong, moderate, low, none.\n"
    "  strong   = clear, material AI/data-center demand (e.g. HBM/AI memory sold to hyperscalers, signed "
    "data-center power deals/PPAs, AI-driven backlog or book-to-bill).\n"
    "  moderate = real but partial, early, or a modest part of the business.\n"
    "  low      = tangential / indirect exposure only.\n"
    "  none     = no discernible AI/data-center angle.\n"
    "STRUCTURAL PRODUCT DEMAND COUNTS: selling AI chips/memory/power/cooling gear into AI buildouts is "
    "real exposure even WITHOUT a single named signed contract. Do not require a signed deal to grade "
    "strong.\n"
    "Classify company type as exactly one of: merchant_gas, nuclear, regulated, renewable, geothermal, "
    "equipment.\n"
    "Output NO financial metrics (market cap, margin, EPS, valuation) — text only.\n"
    "Tag each bullet 'contracted' (signed/binding) or 'aspirational' (exploring/early).\n"
    "In 'comment', give a 2-4 sentence analyst view: how real/strong the AI angle is, what is still "
    "unproven, and the read for a PM. Ground it in the evidence; include no numbers."
)

_SYSTEM_NEWS = (
    _RULES + "\n"
    "You are given a numbered list of REAL recent news items (title, summary, URL). For BULLETS, cite "
    "ONLY the exact URLs from that list, copied verbatim — never invent a URL. You MAY use general "
    "knowledge of the company's business to set the GRADE and comment. If no item evidences exposure, "
    "return empty bullets (the grade can still reflect the company's known business)."
)

_SYSTEM_WEB = (
    _RULES + "\n"
    "Use web search to find the most recent (last ~12 months) AI / data-center / HBM / hyperscaler "
    "demand signals, deals, PPAs, or backlog for this company. For each bullet, include the exact source "
    "URL you found via search (prefer primary/reputable sources). Do not invent URLs."
)

_SCHEMA = ('{"type":"<merchant_gas|nuclear|regulated|renewable|geothermal|equipment>",'
           '"grade":"strong|moderate|low|none","summary":"<=140 chars",'
           '"comment":"<2-4 sentence analyst view>",'
           '"bullets":[{"claim":"...","source":"<URL>","status":"contracted|aspirational"}]}')


@dataclass
class ExposureProposal:
    ticker: str
    company: str
    type: str                       # one of TYPES or "unknown"
    grade: str                      # strong | moderate | low | none | error
    summary: str
    bullets: list = field(default_factory=list)     # [{claim, source, status}]
    comment: str = ""               # the agent's own analyst view (opinion, grounded, no numbers)
    n_sources: int = 0              # how many real news items we gave the model (news mode)
    mode: str = "news"              # 'news' (quick) | 'web' (deep search)
    raw: str = ""
    error: str | None = None


def company_name(ticker: str) -> str:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return info.get("longName") or info.get("shortName") or ticker
    except Exception:
        return ticker


def fetch_news(ticker: str, limit: int = 10) -> list[dict]:
    """Recent news for `ticker` as [{title, summary, url, publisher, date}] — real URLs only."""
    import yfinance as yf
    out = []
    try:
        raw = yf.Ticker(ticker).news or []
    except Exception:
        raw = []
    for it in raw[:limit]:
        c = it.get("content", it) if isinstance(it, dict) else {}
        title = (c.get("title") or "").strip()
        summary = (c.get("summary") or c.get("description") or "").strip()
        url = ""
        for key in ("canonicalUrl", "clickThroughUrl"):
            v = c.get(key)
            if isinstance(v, dict) and str(v.get("url", "")).startswith("http"):
                url = v["url"]
                break
            if isinstance(v, str) and v.startswith("http"):
                url = v
                break
        if not url and isinstance(it, dict) and str(it.get("link", "")).startswith("http"):
            url = it["link"]
        prov = c.get("provider") or {}
        publisher = prov.get("displayName", "") if isinstance(prov, dict) else ""
        if title and url:
            out.append({"title": title, "summary": summary, "url": url,
                        "publisher": publisher, "date": str(c.get("pubDate", ""))})
    return out


def _extract_json(text: str) -> str:
    t = re.sub(r"^```(?:json)?", "", text.strip())
    t = re.sub(r"```$", "", t.strip()).strip()
    m = re.search(r"\{.*\}", t, re.DOTALL)
    return m.group(0) if m else t


def _clean(data: dict, ticker: str, company: str, allowed_urls: set[str] | None, n_sources: int,
           mode: str, raw: str) -> ExposureProposal:
    """Validate the model JSON. `allowed_urls` enforces the source allowlist (news mode); pass None in
    web mode, where URLs come from live search and are shown as verify-before-approve instead."""
    typ = str(data.get("type", "")).strip().lower()
    if typ not in TYPES:
        typ = "unknown"
    grade = str(data.get("grade", "")).strip().lower()
    if grade not in GRADES:
        grade = "none"
    bullets = []
    for b in (data.get("bullets") or []):
        if not isinstance(b, dict):
            continue
        claim = str(b.get("claim", "")).strip()
        src = str(b.get("source", "")).strip()
        status = str(b.get("status", "aspirational")).strip().lower()
        if status not in ("contracted", "aspirational"):
            status = "aspirational"
        ok_src = src.startswith("http") if allowed_urls is None else (src in allowed_urls)
        if claim and ok_src:                               # news mode: URL must be provided; web: real http
            bullets.append({"claim": claim, "source": src, "status": status})
    return ExposureProposal(ticker, company, typ, grade,
                            str(data.get("summary", "")).strip()[:200], bullets,
                            comment=str(data.get("comment", "")).strip()[:800],
                            n_sources=n_sources, mode=mode, raw=raw)


def confirm_exposure(ticker: str, company: str | None = None, deep: bool = False,
                     timeout: int | None = None, retries: int = 2) -> ExposureProposal:
    """Grade `ticker`'s AI-exposure story + propose sourced bullets. `deep=True` uses live web search
    (slower, ~2min) and finds fresh sources; otherwise grounds bullets in recent yfinance news."""
    company = company or company_name(ticker)
    news = fetch_news(ticker)
    listing = "\n".join(
        f"[{i}] {n['title']} — {n['summary'][:200]}\n    URL: {n['url']}"
        for i, n in enumerate(news, 1)) or "(no recent news items available)"

    if deep:
        system, allowed, mode, tmo, yolo = _SYSTEM_WEB, None, "web", (timeout or 240), True
        base = (f"Company: {company} (ticker {ticker}).\n"
                f"Search the web for this company's most recent AI / data-center demand signals, deals, "
                f"PPAs, HBM/memory allocations, or backlog. For extra context, recent headlines:\n{listing}\n\n"
                f"Output JSON exactly in this shape:\n{_SCHEMA}")
    else:
        system, allowed, mode, tmo, yolo = _SYSTEM_NEWS, {n["url"] for n in news}, "news", (timeout or 180), False
        base = (f"Company: {company} (ticker {ticker}).\nReal recent news items:\n{listing}\n\n"
                f"Grade the AI/data-center exposure; for bullets cite ONLY the exact URLs above. "
                f"Output JSON exactly in this shape:\n{_SCHEMA}")

    prompt, raw, last_err = base, "", None
    for _ in range(max(1, retries)):
        try:
            raw = call_gemini(prompt, system=system, timeout=tmo, yolo=yolo)
        except GeminiError as e:
            return ExposureProposal(ticker, company, "unknown", "error", "", n_sources=len(news),
                                    mode=mode, error=str(e))
        try:
            return _clean(json.loads(_extract_json(raw)), ticker, company, allowed, len(news), mode, raw)
        except Exception as e:
            last_err = f"could not parse JSON ({e})"
            prompt = base + "\n\nReturn ONLY the JSON object — no prose, no code fences."
    return ExposureProposal(ticker, company, "unknown", "error", "", n_sources=len(news),
                            mode=mode, raw=raw, error=last_err)
