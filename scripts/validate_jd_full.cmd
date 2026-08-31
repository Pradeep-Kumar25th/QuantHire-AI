@echo off
setlocal EnableExtensions
cd /d "%~dp0.."

set "FAILED=0"
set "STEP=0"
set "TOTAL=7"

echo.
echo ============================================================
echo   QuantHire AI - Full JD E2E Validation
echo   Job card ^| QuantChat ^| PDF ^| Save pipeline ^| HITL
echo ============================================================
echo.
echo Run this from CMD in the repo root (or double-click this file).
echo.

call :step "JD customization HITL E2E simulation + wiring"
python scripts\validate_jd_customization_e2e.py --skip-pytest
if errorlevel 1 goto :fail_pytest

call :step "Python syntax check (JD backend + QuantChat)"
python -m py_compile "apps\quantchat\ingestion\chunking.py" "apps\api\app\services\pgvector_ingestion.py" "apps\api\app\services\jd_pipeline_service.py" "apps\api\app\services\jd_generation_tasks.py" "apps\api\app\api\v1\jd_generation.py"
if errorlevel 1 goto :fail_syntax

call :step "Frontend TypeScript type-check"
pushd "apps\web"
call npm run type-check
set "TS_ERR=%ERRORLEVEL%"
popd
if not "%TS_ERR%"=="0" goto :fail_typescript

call :step "Save pipeline + denormalization tests"
set PYTHONUNBUFFERED=1
python -m pytest tests\unit\test_jd_pipeline_service.py -v --tb=short
if errorlevel 1 goto :fail_pytest

call :step "HITL chunking + section numbering + QuantChat full-doc tests"
python -m pytest tests\unit\test_jd_hitl_chunking.py tests\unit\test_jd_section_numbering.py tests\unit\test_jd_quantchat_full_doc.py -v --tb=short
if errorlevel 1 goto :fail_pytest

call :step "Reopen workflow + E2E sync tests (job card, title fix, PDF wiring)"
python -m pytest tests\unit\test_jd_reopen_workflow.py tests\unit\test_jd_e2e_sync.py -v --tb=short
if errorlevel 1 goto :fail_pytest

call :step "JD generation workflow tests"
python -m pytest tests\unit\test_jd_generation_async.py tests\unit\test_jd_generation_workflow.py -v --tb=short
if errorlevel 1 goto :fail_pytest

echo.
echo ============================================================
echo   ALL AUTOMATED CHECKS PASSED
echo ============================================================
echo.
echo Manual UAT checklist (browser, after npm run dev or NPD deploy):
echo.
echo  JOB CARD PREVIEW
echo   [ ] Edit 1a. Job Title - Save to pgvector - card title updates
echo   [ ] Edit department/team/division - card subtitle updates
echo   [ ] Edit job level - card level badge updates
echo   [ ] Remove a JD section - card shows "Customized JD (N sections hidden)"
echo   [ ] Add custom section - card shows "+N custom" badge
echo   [ ] Card shows summary snippet and skill tags from saved JD
echo.
echo  JD EDITOR / SAVE
echo   [ ] Apply Changes alone does NOT update job card or QuantChat
echo   [ ] Save to pgvector updates job card immediately (jobsUpdated event)
echo   [ ] Close and reopen JD - all edits persisted (title, sections, custom)
echo   [ ] Regenerate warns when unsaved edits exist
echo.
echo  QUANTCHAT (after Save to pgvector)
echo   [ ] Ask about the job by NEW title - full JD returned
echo   [ ] Removed section content is NOT in QuantChat answer
echo   [ ] Custom section content IS queryable (e.g. Travel Policy)
echo   [ ] Department/team edits appear in QuantChat full-doc response
echo.
echo  PDF DOWNLOAD
echo   [ ] Download PDF - removed sections are absent
echo   [ ] Custom sections appear with correct dynamic numbering
echo   [ ] Edited title, level, location, and org fields appear in PDF
echo.
echo Quick re-run options:
echo   scripts\validate_jd_full.cmd              ^<- this full suite
echo   scripts\validate_jd_customization_e2e.cmd ^<- card click + HITL E2E
echo   scripts\validate_jd_hitl.cmd              ^<- backend HITL only
echo   scripts\validate_jd_reopen.cmd            ^<- reopen + TypeScript only
echo.
exit /b 0

:step
set /a STEP+=1
echo.
echo ------------------------------------------------------------
echo  STEP %STEP%/%TOTAL%: %~1
echo ------------------------------------------------------------
exit /b 0

:fail_syntax
echo.
echo FAIL: Python syntax check failed.
set FAILED=1
goto :done

:fail_typescript
echo.
echo FAIL: TypeScript type-check failed.
set FAILED=1
goto :done

:fail_pytest
echo.
echo FAIL: pytest failed. Scroll up for the first FAILED test name.
set FAILED=1
goto :done

:done
if "%FAILED%"=="1" (
  echo.
  echo ============================================================
  echo   VALIDATION FAILED - fix errors above and re-run
  echo ============================================================
  exit /b 1
)
