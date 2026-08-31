@echo off
REM Pre-deploy SSO validation — run from repo root in cmd.exe
setlocal EnableExtensions
cd /d "%~dp0.."

set PYTHONPATH=apps\api;apps\agents;apps\agents\agents
set JWT_SECRET_KEY=unit-test-jwt-secret-key-32chars-min
set APP_ENV=testing

echo === SSO static validation ===
python scripts\validate_sso_implementation.py
if errorlevel 1 (
  echo.
  echo SSO pre-deploy validation FAILED at static checks.
  exit /b 1
)

echo === HR recruiter SSO validation ===
python scripts\validate_hr_recruiter_sso.py
if errorlevel 1 (
  echo.
  echo HR recruiter SSO validation FAILED.
  exit /b 1
)

echo.
echo === SSO unit tests ===
python -m pytest tests\unit\test_entra_auth.py tests\unit\test_auth_entra.py tests\unit\test_entra_user_upsert.py tests\unit\test_coerce_user_role.py tests\unit\test_sso_e2e_flow.py tests\unit\test_recruiter_role_casing.py -v --tb=short
if errorlevel 1 (
  echo.
  echo SSO pre-deploy validation FAILED at unit tests.
  exit /b 1
)

echo.
echo SSO pre-deploy validation PASSED.
exit /b 0
