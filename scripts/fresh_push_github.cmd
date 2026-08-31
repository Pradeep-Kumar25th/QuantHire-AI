@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

echo.
echo ============================================================
echo  QuantHire - Fresh GitHub push (wipes ALL remote history)
echo  Repo: https://github.com/Pradeep-Kumar25th/QuantHire-AI
echo ============================================================
echo.
echo This will:
echo   1. Create a brand-new git history locally (orphan branch)
echo   2. Commit ONLY the latest project code (one commit)
echo   3. Force-push to origin/main and REPLACE everything on GitHub
echo.
echo Old commits and old files on GitHub will be PERMANENTLY removed.
echo.
set /p CONFIRM=Type YES to continue: 
if /i not "%CONFIRM%"=="YES" (
  echo Cancelled.
  exit /b 1
)

echo.
echo [1/6] Creating orphan branch (no parent commits)...
git checkout --orphan fresh-start
if errorlevel 1 goto :fail

echo [2/6] Clearing index...
git rm -rf --cached . >nul 2>&1

echo [3/6] Staging latest codebase...
git add apps/ tests/ scripts/ infra/ models/ .github/
git add Dockerfile.backend Dockerfile.frontend README.md .env.example .dockerignore .gitignore
if exist requirements-complete.txt git add requirements-complete.txt
if exist grafana-datasource.json git add grafana-datasource.json
if exist RUN_PACK_HELM.cmd git add RUN_PACK_HELM.cmd
if exist output\hazim_review git add output/hazim_review/

echo [4/6] Committing single snapshot...
git commit -m "QuantHire Phase 1 final build (NPD 0.1.5): full codebase"
if errorlevel 1 (
  echo.
  echo Commit failed. If Git asks for user.name/email, run:
  echo   git config user.email "your@email.com"
  echo   git config user.name "Your Name"
  echo Then run this script again.
  goto :fail
)

echo [5/6] Renaming branch to main...
git branch -M main

echo [6/6] Force-pushing to GitHub (replaces all remote history)...
git push --force origin main
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  SUCCESS - GitHub now has ONE commit with latest code only.
echo  Verify: https://github.com/Pradeep-Kumar25th/QuantHire-AI
echo ============================================================
exit /b 0

:fail
echo.
echo FAILED. Fix the error above and re-run this script.
exit /b 1
