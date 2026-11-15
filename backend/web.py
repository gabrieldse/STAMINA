"""Serve the built website and scientific API on a single origin.

Run from the repository root after `npm run build` in frontend:
    python -m uvicorn backend.web:app --host 127.0.0.1 --port 8080
"""
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from backend.api import app

DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if not (DIST / "index.html").is_file():
    raise RuntimeError("Build the website first: cd frontend && npm run build")

# API routes are registered first; only the production assets are public.
app.mount("/", StaticFiles(directory=DIST, html=True), name="website")
