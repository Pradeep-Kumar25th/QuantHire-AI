@echo off
setlocal
cd /d "%~dp0.."
echo === JD reopen / view-edit validation ===
echo.

echo [1/3] Frontend TypeScript check...
cd apps\web
call npm run type-check
if errorlevel 1 (
  echo FAIL: TypeScript type-check
  exit /b 1
)
cd ..\..
echo OK: TypeScript type-check
echo.

echo [2/3] Unit tests (reopen + E2E sync + HITL + pipeline + QuantChat)...
set PYTHONUNBUFFERED=1
python -m pytest tests\unit\test_jd_reopen_workflow.py tests\unit\test_jd_e2e_sync.py tests\unit\test_jd_pipeline_service.py tests\unit\test_jd_hitl_chunking.py tests\unit\test_jd_section_numbering.py tests\unit\test_jd_quantchat_full_doc.py tests\unit\test_jd_generation_async.py -v --tb=short
if errorlevel 1 (
  echo FAIL: pytest
  exit /b 1
)
echo.

echo [3/3] Manual UAT checklist (after deploy or npm run dev):
echo   1. Jobs list shows "AI JD" badge on AI-generated roles
echo   2. Click job card - opens "View ^& Edit Job Description" dialog
echo   3. Preview tab shows all enterprise sections
echo   4. Edit All Sections - remove/add section - Apply - unsaved banner stays
echo   5. Save to pgvector - same job_id, banner clears, jobs list refreshes
echo   6. Close and reopen card - edits persisted
echo   7. QuantChat - removed section not found; custom section queryable
echo   8. Job detail page - "Edit AI JD" button opens same dialog
echo   9. Regenerate optional - confirm if unsaved edits exist
echo.
echo ALL JD REOPEN CHECKS PASSED
exit /b 0
