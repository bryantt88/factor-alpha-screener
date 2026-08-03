# Hugging Face Space (Docker) — runs the whole app in one container:
# FastAPI serves the pre-built front-end (web/out) AND the /api endpoints on port 7860.
FROM python:3.12-slim

WORKDIR /app

# Install Python deps first (layer-cached).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code (src/, config.yaml, and the pre-built front-end in web/out).
COPY . .

# HF Spaces route traffic to port 7860 (see app_port in README front-matter).
ENV PORT=7860
EXPOSE 7860
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "7860"]
