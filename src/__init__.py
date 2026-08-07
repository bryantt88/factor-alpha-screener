"""Factor-Alpha Screener — scorecard + regression pipeline.

A factor-model / performance-driver engine: for any liquid market it isolates each stock's
idiosyncratic return (alpha + residual) from common factors and turns it into market-neutral
trade ideas. See docs/SPEC.md for the full design and CLAUDE.md for the hard rules.

Build order (back-to-front, a working artifact at each step):
    1. regression/ + viz/   2. gates/   3. data/fundamentals/   4. agent/   5. knowledge_base/ + app/
"""

__version__ = "0.0.0"
