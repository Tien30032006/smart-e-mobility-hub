@echo off
cd /d %~dp0\..
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -q -r requirements.txt
if not exist .env copy .env.example .env
echo Open http://localhost:8000/app/login.html
uvicorn src.backend.app:app --host 0.0.0.0 --port 8000
