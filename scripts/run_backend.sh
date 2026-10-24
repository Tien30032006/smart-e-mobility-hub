#!/usr/bin/env bash
# Run from anywhere: starts API + frontend on http://localhost:8000  (Swagger: /docs, UI: /app/)
cd "$(dirname "$0")/.." && uvicorn src.backend.app:app --reload --port 8000
