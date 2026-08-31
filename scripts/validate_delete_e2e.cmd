@echo off

setlocal EnableExtensions

cd /d "%~dp0.."

echo.

echo ============================================================

echo   DELETE Full Validation - Every Aspect

echo   Jobs/JDs ^| Resumes ^| QuantChat ^| Matching ^| UI ^| API

echo   Run from CMD in repo root

echo ============================================================

echo.

set PYTHONUNBUFFERED=1

python scripts\validate_delete_e2e.py %*

set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (

  echo.

  echo Validation failed with exit code %EXIT_CODE%.

  exit /b %EXIT_CODE%

)

echo.

echo All delete aspects validated. See manual UAT checklist above.

exit /b 0
