"""AI-Power Stack Screener — scorecard + regression pipeline.

Finds mid-to-large-cap US-listed AI-power-stack stocks with a genuine, commodity-adjusted
AI uptrend. See docs/SPEC.md for the full design and CLAUDE.md for the hard rules.

Build order (back-to-front, a working artifact at each step):
    1. regression/ + viz/   2. gates/   3. data/fundamentals/   4. agent/   5. knowledge_base/ + app/
"""

__version__ = "0.0.0"
