@echo off
setlocal
cd /d "%~dp0.."

set NS=quanthire-nonprod
set SCRIPT=apps\api\scripts\fix_xx4_entra_user.py

echo ============================================================
echo Fix xx4 VIEWER SSO on AKS (Jump VM)
echo ============================================================
echo.

if not exist "%SCRIPT%" (
  echo Missing %SCRIPT%
  exit /b 1
)

echo [1] API pods:
kubectl get pods -n %NS% -l app.kubernetes.io/component=api
echo.

for /f "delims=" %%i in ('kubectl get pod -n %NS% -l app.kubernetes.io/component=api -o jsonpath^="{.items[?(@.status.phase=='Running')].metadata.name}"') do set POD=%%i

if "%POD%"=="" (
  echo No Running API pod found.
  exit /b 1
)

echo Using pod: %POD%
echo.

echo [2] Copy fix script into pod...
kubectl cp "%SCRIPT%" %NS%/%POD%:/tmp/fix_xx4.py
if errorlevel 1 exit /b 1

echo [3] Run DB fix...
kubectl exec -n %NS% %POD% -- python /tmp/fix_xx4.py
if errorlevel 1 (
  echo.
  echo FAILED. Logs:
  kubectl logs -n %NS% %POD% --tail=80
  exit /b 1
)

echo.
echo [4] SUCCESS. Test xx4 in browser:
echo   https://quanthire-npd.malomatia.com/login
echo   Sign in with Microsoft - xx4@malomatia.com
echo.
endlocal
