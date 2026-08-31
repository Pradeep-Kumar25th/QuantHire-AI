@echo off
REM Packages the FIXED Helm chart (infra\kubernetes\helm) into helm_base64_latest.txt
REM for clipboard transfer to the Azure Bastion Jump VM.
cd /d "%~dp0"
python scripts\packaging\helm_to_base64.py
if errorlevel 1 (
  echo.
  echo FAILED - check that Python is installed and on PATH.
) else (
  echo.
  echo DONE - copy the contents of helm_base64_latest.txt to the Jump VM.
)
pause
