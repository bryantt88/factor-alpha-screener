"""HTTP API layer — a thin FastAPI wrapper over the same run_screen() the CLI and Streamlit use.

This exists so a React/Next.js front-end (the chosen platform) can drive the exact same analytics
pipeline. Nothing analytical lives here: the API only orchestrates run_screen + serialises the result
to JSON. See src/api/server.py (endpoints) and src/api/serialize.py (JSON contract).
"""
