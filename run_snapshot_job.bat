@echo off
cd /d "%~dp0"
.venv\Scripts\python.exe -m src.pipeline.scheduled_job >> data\logs\scheduled_job.log 2>&1
