@echo off
echo ============================================================
echo RAG-Anything OCR Service - Full Stack
echo ============================================================
echo.

:: Start Celery Worker in new window
echo Starting Celery Worker...
start "Celery Worker" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && celery -A app.queue.celery_app worker -Q ocr,index,convert,default -l info -P solo"

:: Wait a moment for Celery to start
timeout /t 3 /nobreak > nul

:: Start FastAPI Server
echo Starting FastAPI Server...
echo.
echo Server: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Press CTRL+C to stop server (close Celery window manually)
echo ============================================================
echo.

call .venv\Scripts\activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
