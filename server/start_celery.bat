@echo off
echo Starting Celery Worker...
echo.
cd /d %~dp0
call .venv\Scripts\activate
celery -A app.queue.celery_app worker -Q ocr,index,convert,default,enrichment -l info -P solo
