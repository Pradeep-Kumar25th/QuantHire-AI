@echo off
setlocal
cd /d "%~dp0.."
echo === JD generation + HITL validation ===
echo.

python -m py_compile "apps\quantchat\ingestion\chunking.py" "apps\api\app\services\pgvector_ingestion.py" "apps\api\app\services\jd_pipeline_service.py" "apps\api\app\services\jd_generation_tasks.py" "apps\api\app\api\v1\jd_generation.py"
if errorlevel 1 (
  echo FAIL: Python syntax check
  exit /b 1
)
echo OK: Python syntax check
echo.

echo Running pytest (HITL + pipeline + QuantChat + generation)...
echo.
set PYTHONUNBUFFERED=1
python -m pytest tests\unit\test_jd_hitl_chunking.py tests\unit\test_jd_pipeline_service.py tests\unit\test_jd_section_numbering.py tests\unit\test_jd_quantchat_full_doc.py tests\unit\test_jd_generation_async.py tests\unit\test_jd_generation_workflow.py -v --tb=short
if errorlevel 1 (
  echo.
  echo FAIL: pytest
  exit /b 1
)
echo.
echo ALL JD HITL CHECKS PASSED
exit /b 0
