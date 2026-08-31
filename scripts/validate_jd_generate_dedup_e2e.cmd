@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo.
echo ============================================================
echo   JD Generate Dedup Fix Validation
echo ============================================================
echo.

set PYTHONUNBUFFERED=1
python scripts\validate_jd_generate_dedup_e2e.py %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Validation failed with exit code %EXIT_CODE%.
  exit /b %EXIT_CODE%
)

echo Done.
exit /b 0
