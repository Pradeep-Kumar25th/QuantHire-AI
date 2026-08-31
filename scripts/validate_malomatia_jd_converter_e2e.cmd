@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo  QuantHire AI - End-to-End Malomatia JD Converter Validator
echo =====================================================================

cd /d "%~dp0\.."

if exist "venv\Scripts\python.exe" (
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo Using Python: !PYTHON_EXE!

rem Malomatia export uses python-docx (bundled in API container; optional in root venv)
!PYTHON_EXE! -c "import docx" >nul 2>&1
if errorlevel 1 (
    echo Installing python-docx into local venv for validation...
    !PYTHON_EXE! -m pip install "python-docx==1.1.0"
    if errorlevel 1 (
        echo [ERROR] Failed to install python-docx. Run: !PYTHON_EXE! -m pip install python-docx==1.1.0
        exit /b 1
    )
)

echo Running validation suite...
echo.

!PYTHON_EXE! scripts\validate_malomatia_jd_converter_e2e.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Validation failed with exit code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo.
echo [SUCCESS] Validation complete!
