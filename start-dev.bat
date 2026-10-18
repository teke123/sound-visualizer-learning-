@echo off
rem Start backend (0.0.0.0:8000) and frontend (0.0.0.0:5173).
rem Frontend: http://<local-ip>:5173   Backend docs: http://<local-ip>:8000/docs

setlocal
cd /d "%~dp0"

rem Backend reads SVS_HOST env var (see backend/app/config.py, default 127.0.0.1)
start "backend :8000" cmd /k "cd /d "%~dp0backend" && (py -3 main.py || (echo [ERROR] py -3 failed, check Python 3.11+ on PATH) & pause)"

rem --host overrides the 127.0.0.1 pinned in vite.config.ts
start "frontend :5173" cmd /k "cd /d "%~dp0" && npm run dev -- --host 0.0.0.0"

endlocal
