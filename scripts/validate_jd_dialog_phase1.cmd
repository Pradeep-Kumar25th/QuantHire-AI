@echo off

setlocal EnableExtensions

cd /d "%~dp0.."

echo.

echo ============================================================

echo   JD Generation Dialog - Phase 1 HR UX Validation

echo   Copy ^| merged save ^| titles ^| confirms ^| success message

echo   Run from CMD in repo root

echo ============================================================

echo.

set PYTHONUNBUFFERED=1

python scripts\validate_jd_dialog_phase1.py %*

set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (

  echo.

  echo Validation failed with exit code %EXIT_CODE%.

  exit /b %EXIT_CODE%

)

echo.

echo JD dialog Phase 1 checks passed. Complete manual UAT checklist above.

exit /b 0
