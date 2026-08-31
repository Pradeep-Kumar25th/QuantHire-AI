@echo off
setlocal
cd /d "%~dp0.."

echo === QuantHire security remediation validation ===
python -m pip install -q pytest pytest-asyncio httpx pyjwt cryptography 2>nul

set PYTHONPATH=%CD%\apps\api;%CD%\apps\agents\src
python -m pytest tests\unit\test_security_remediation.py tests\unit\test_session_cookie.py tests\unit\test_entra_auth.py tests\unit\test_auth_entra.py -q --tb=short
if errorlevel 1 (
  echo SECURITY VALIDATION FAILED
  exit /b 1
)
echo ALL SECURITY CHECKS PASSED
exit /b 0
