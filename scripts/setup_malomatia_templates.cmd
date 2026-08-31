@echo off
setlocal
cd /d "%~dp0.."
python scripts\setup_malomatia_templates.py
exit /b %ERRORLEVEL%
