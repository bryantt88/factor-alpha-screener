"""App-layer server helpers used by the API.

The interactive UI is the Next.js front-end in `web/` (served by FastAPI at one origin — see
`src/api/server.py`). This package now holds only server-side helpers: `explain.py`, the optional
Gemini "how to read" explainer that describes the computed numbers in plain language (it never
invents any). The earlier Streamlit prototype has been removed.
"""
