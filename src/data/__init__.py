"""Data layer (docs/DATA.md): prices/returns, market cap, swappable fundamentals backend.

A source abstraction so the rest of the model never hardcodes a provider. The regression core
depends only on free public price data, so it is buildable/testable immediately.
"""
