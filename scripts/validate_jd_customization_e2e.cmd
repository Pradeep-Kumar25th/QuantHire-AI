@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo.
echo ============================================================
echo   QuantHire AI - JD Customization HITL E2E Validation
echo   Run from CMD in repo root (or double-click this file)
echo ============================================================
echo.

set PYTHONUNBUFFERED=1
python scripts\validate_jd_customization_e2e.py %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Validation failed with exit code %EXIT_CODE%.
  exit /b %EXIT_CODE%
)

echo.
echo Done. See manual UAT checklist above for browser verification.
exit /b 0
