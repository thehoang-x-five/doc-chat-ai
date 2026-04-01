@echo off
REM Quick start script for RAG-Anything Backend

echo ========================================
echo   RAG-Anything Backend Server
echo ========================================
echo.

cd server

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

echo Activating virtual environment...
call .venv\Scripts\activate

if not exist .env (
    echo.
    echo WARNING: .env file not found!
    echo Please copy .env.example to .env and configure it.
    echo.
    pause
    exit /b 1
)

echo Installing dependencies...
pip install -q -r requirements.txt

echo.
echo Starting server...
echo Server will be available at: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.

python start_server.py
