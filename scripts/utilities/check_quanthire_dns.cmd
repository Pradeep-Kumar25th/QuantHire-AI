@echo off
setlocal
echo ============================================================
echo QuantHire DNS / HTTPS check — quanthire-npd.malomatia.com
echo Run this on the Azure VM (corporate DNS) Hazim mentioned.
echo ============================================================
echo.

echo [1] Default DNS resolver on this machine:
nslookup quanthire-npd.malomatia.com
echo.

echo [2] Google public DNS (8.8.8.8):
nslookup quanthire-npd.malomatia.com 8.8.8.8
echo.

echo [3] HTTP probe (LoadBalancer IP fallback):
curl.exe -sI --connect-timeout 10 http://10.250.208.31/login
echo.

echo [4] HTTPS probe (hostname — needs DNS + cert):
curl.exe -skI --connect-timeout 10 https://quanthire-npd.malomatia.com/login
echo.

echo [5] HTTP probe (hostname):
curl.exe -sI --connect-timeout 10 http://quanthire-npd.malomatia.com/login
echo.

echo Done. Expected on VM with DNS: step 1 returns an IP; step 4 returns HTTP 200/301/302.
echo NXDOMAIN on laptop = internal DNS only — use VM or VPN.
endlocal
