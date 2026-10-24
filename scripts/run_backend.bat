@echo off
cd /d %~dp0\..
uvicorn src.backend.app:app --reload --port 8000
