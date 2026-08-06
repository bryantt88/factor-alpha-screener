"""Opportunity layer — turns the factor-model output into actionable, threshold-gated trade ideas.

Pure synthesis on top of the regression + variance decomposition already computed per stock (no new
model fitting). See opportunity/engine.py. Consumed by api/serialize.py -> the React 'Opportunity' panel.
"""
from .engine import build_opportunities  # noqa: F401
