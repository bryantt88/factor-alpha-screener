"""Industry-average valuation multiples + margins, for benchmarking a stock against its industry.

Source: Aswath Damodaran / NYU Stern, "Last Updated in January 2026" (the standard free PM reference).
These are REAL published figures transcribed from his public datasets — never estimated (CLAUDE.md
rule 2). Refresh ~yearly from:
  https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/vebitda.html   (EV/EBITDA)
  https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/pedata.html    (P/E)
  https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/margin.html    (margins)

Each stock is mapped to a Damodaran industry via its yfinance industry/sector string (keyword match).
Unmapped -> None (no benchmark shown, never faked).
"""
from __future__ import annotations

DAMODARAN_DATE = "Jan 2026"

# industry -> {ev_ebitda, pe, ebitda_margin (decimal), net_margin (decimal)}
_TABLE: dict[str, dict] = {
    "Semiconductor":                        {"ev_ebitda": 34.75, "pe": 100.18, "ebitda_margin": 0.3677, "net_margin": 0.3045},
    "Semiconductor Equipment":              {"ev_ebitda": 24.74, "pe": 46.83,  "ebitda_margin": 0.2906, "net_margin": 0.2132},
    "Software (System & Application)":      {"ev_ebitda": 24.48, "pe": 79.17,  "ebitda_margin": 0.3593, "net_margin": 0.2549},
    "Software (Internet)":                  {"ev_ebitda": 30.26, "pe": 67.21,  "ebitda_margin": 0.0952, "net_margin": -0.0093},
    "Computers/Peripherals":                {"ev_ebitda": 25.42, "pe": 81.13,  "ebitda_margin": 0.2532, "net_margin": 0.1778},
    "Computer Services":                    {"ev_ebitda": 14.10, "pe": 51.60,  "ebitda_margin": 0.0898, "net_margin": 0.0445},
    "Electrical Equipment":                 {"ev_ebitda": 24.59, "pe": 80.04,  "ebitda_margin": 0.1265, "net_margin": 0.0094},
    "Power (Utilities)":                    {"ev_ebitda": 12.38, "pe": 24.74,  "ebitda_margin": 0.3533, "net_margin": 0.1273},
    "Green & Renewable Energy":             {"ev_ebitda": 13.44, "pe": 32.25,  "ebitda_margin": 0.5845, "net_margin": -0.1083},
    "Utility (General)":                    {"ev_ebitda": 13.73, "pe": 19.92,  "ebitda_margin": 0.3492, "net_margin": 0.1418},
    "Utility (Water)":                      {"ev_ebitda": 14.14, "pe": 23.07,  "ebitda_margin": 0.4573, "net_margin": 0.2116},
    "Oil/Gas (Integrated)":                 {"ev_ebitda": 8.16,  "pe": 16.24,  "ebitda_margin": 0.2167, "net_margin": 0.0830},
    "Oil/Gas (Production & Exploration)":   {"ev_ebitda": 5.15,  "pe": 30.98,  "ebitda_margin": 0.4321, "net_margin": 0.1463},
    "Oilfield Services/Equipment":          {"ev_ebitda": 8.63,  "pe": 33.30,  "ebitda_margin": 0.0776, "net_margin": 0.0234},
    "Telecom (Wireless)":                   {"ev_ebitda": 8.97,  "pe": 107.14, "ebitda_margin": 0.3457, "net_margin": 0.1224},
    "Telecom Services":                     {"ev_ebitda": 6.54,  "pe": 16.79,  "ebitda_margin": 0.3470, "net_margin": 0.1420},
}

# yfinance "industry | sector" (lowercased) -> Damodaran industry. Order matters: first hit wins, so
# the more specific keywords are listed before the broad ones.
_KEYWORDS: list[tuple[str, str]] = [
    ("semiconductor equipment", "Semiconductor Equipment"),
    ("semiconductor", "Semiconductor"),
    ("internet content", "Software (Internet)"),
    ("internet retail", "Software (Internet)"),
    ("software", "Software (System & Application)"),
    ("information technology services", "Computer Services"),
    ("computer hardware", "Computers/Peripherals"),
    ("communication equipment", "Electrical Equipment"),
    ("electrical equipment", "Electrical Equipment"),
    ("specialty industrial machinery", "Electrical Equipment"),
    ("renewable", "Green & Renewable Energy"),
    ("solar", "Green & Renewable Energy"),
    ("independent power", "Power (Utilities)"),
    ("regulated water", "Utility (Water)"),
    ("regulated electric", "Utility (General)"),
    ("regulated gas", "Utility (General)"),
    ("diversified utilities", "Utility (General)"),
    ("utilities", "Utility (General)"),
    ("oil & gas integrated", "Oil/Gas (Integrated)"),
    ("oil & gas e&p", "Oil/Gas (Production & Exploration)"),
    ("oil & gas exploration", "Oil/Gas (Production & Exploration)"),
    ("oil & gas equipment", "Oilfield Services/Equipment"),
    ("oil & gas drilling", "Oilfield Services/Equipment"),
    ("telecom", "Telecom Services"),
]

_INDUSTRY_CACHE: dict[str, tuple] = {}


def _industry_string(ticker: str) -> str:
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        return f"{info.get('industry') or ''} | {info.get('sector') or ''}"
    except Exception:
        return ""


def benchmark_for(ticker: str) -> dict | None:
    """{'name', 'source', 'ev_ebitda', 'pe', 'ebitda_margin', 'net_margin'} for `ticker`'s Damodaran
    industry, or None if we can't confidently map it (never guessed)."""
    tk = ticker.upper()
    if tk in _INDUSTRY_CACHE:
        return _INDUSTRY_CACHE[tk]
    s = _industry_string(ticker).lower()
    result = None
    for kw, ind in _KEYWORDS:
        if kw in s:
            result = {"name": ind, "source": f"Damodaran {DAMODARAN_DATE}", **_TABLE[ind]}
            break
    _INDUSTRY_CACHE[tk] = result
    return result
