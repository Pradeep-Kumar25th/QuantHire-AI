@echo off

REM QuantHire Non-Prod — full Azure UAT validation (run on Jump VM after deploy)

set NS=quanthire-nonprod

set FE=http://10.250.208.29



echo === 1. Pods ===

kubectl get pods -n %NS% -o wide



echo.

echo === 2. Services ===

kubectl get svc -n %NS% -o wide



echo.

echo === 3. API readyz ===

kubectl exec deploy/quanthire-nonprod-api -n %NS% -- curl -sf -H "Host: localhost" http://127.0.0.1:8000/readyz

if errorlevel 1 (echo FAIL: readyz) else (echo OK: readyz)



echo.

echo === 4. BFF health (in-pod) ===

kubectl exec deploy/quanthire-nonprod-web -n %NS% -- wget -qO- http://127.0.0.1:3000/api/health



echo.

echo === 5. BFF health (LoadBalancer — same as browser) ===

curl -sf %FE%/api/health

if errorlevel 1 (echo FAIL: LB /api/health) else (echo OK: LB /api/health)



echo.

echo === 6. Standalone frontend check ===

kubectl exec deploy/quanthire-nonprod-web -n %NS% -- sh -c "test -f /app/server.js && echo STANDALONE=YES || echo STANDALONE=NO"



echo.

echo === 7. Azure env in API pod ===

kubectl exec deploy/quanthire-nonprod-api -n %NS% -- sh -c "echo DEPLOYMENT_TARGET=$DEPLOYMENT_TARGET VECTOR_STORE=$VECTOR_STORE MILVUS_ENABLED=$MILVUS_ENABLED"



echo.

echo === 8. Job matching health ===

curl -sf %FE%/api/v1/job-matching/health

if errorlevel 1 (echo FAIL: job-matching health) else (echo OK: job-matching health)



echo.

echo === 9. QuantChat status ===

curl -sf %FE%/api/v1/quantchat/status

if errorlevel 1 (echo FAIL: quantchat status) else (echo OK: quantchat status)



echo.

echo === 10. List endpoints (need login token for 401 without auth) ===

curl -s -o NUL -w "job-matching/candidates HTTP %%{http_code}\n" %FE%/api/v1/job-matching/candidates



echo.

echo Done. Login at %FE%/login then test JD, Resume upload, QuantChat, and Match in browser.

