"""Platform / UI layer (docs/PLATFORM.md) — build-order step 5, framework-NEUTRAL until then.

Project decision: the web framework (Streamlit vs Reflex vs ...) is deliberately NOT chosen yet;
it is locked at step 5, informed by real CLI usage. Whatever is chosen, it will IMPORT and call
src.main.run_screen() and the same pipeline functions — the UI is a convenience layer, not a rewrite.
Three pages: New Run, Results Dashboard, History / Knowledge Base.
"""
