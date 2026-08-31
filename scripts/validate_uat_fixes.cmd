@echo off
setlocal
cd /d "%~dp0.."
echo === QuantHire UAT fix validation ===
echo.

python -m py_compile "apps\quantchat\core\intent_classifier.py" "apps\api\app\api\v1\quantchat.py" "apps\api\app\core\query_router_lifecycle.py" "apps\agents\agents\deployment_env.py" "apps\agents\agents\langgraph_checkpointer.py" "apps\agents\agents\jd_generation\state_machine.py" "apps\agents\agents\jd_generation\orchestrator.py" "apps\api\app\services\resume_profile_converter.py" "apps\api\app\services\resume_pipeline_service.py" "apps\api\app\api\v1\resume_parsing.py" "apps\api\app\api\v1\job_matching.py"
if errorlevel 1 (
  echo FAIL: Python syntax check
  exit /b 1
)
echo OK: Python syntax check
echo.

python -m pytest tests\unit\test_uat_fixes_validation.py tests\unit\test_jd_generation_workflow.py tests\unit\test_resume_parsing_workflow.py tests\unit\test_job_matching_workflow.py tests\unit\test_intent_classifier.py tests\unit\test_chat_factory_paths.py tests\unit\test_azure_env_sync.py tests\unit\test_database_import.py tests\unit\test_dockerfiles.py tests\unit\test_nonprod_manifest.py tests\unit\test_azure_deployment.py tests\unit\test_blockers.py -q --tb=short
if errorlevel 1 (
  echo FAIL: pytest
  exit /b 1
)
echo.
echo ALL CHECKS PASSED
exit /b 0
