@echo off
REM Start RepoPilot from the backend directory.
REM Limit autoreload to application code so uploaded repositories in storage/
REM cannot trigger a server restart while a test job is running.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir app
