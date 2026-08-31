import sys
import os

# Add apps/agents to path
sys.path.append(os.path.join(os.getcwd(), "apps", "agents"))

try:
    from agents.jd_generation.enterprise_prompts import ENTERPRISE_JD_GENERATION_PROMPT
    
    # Test values
    values = {
        "job_title": "Software Engineer",
        "job_level": "Senior",
        "department": "Engineering",
        "location": "Doha",
        "remote_allowed": "Yes",
        "work_model": "Remote",
        "user_requirements": "None"
    }
    
    print("Testing ENTERPRISE_JD_GENERATION_PROMPT.format()...")
    try:
        ENTERPRISE_JD_GENERATION_PROMPT.format(**values)
        print("✅ Success!")
    except ValueError as e:
        print(f"❌ Failed: {e}")
        # Try to find where it fails by splitting
        lines = ENTERPRISE_JD_GENERATION_PROMPT.split("\n")
        for i, line in enumerate(lines):
            try:
                line.format(**values)
            except ValueError:
                print(f"Error on line {i+1}: {line}")

except Exception as e:
    print(f"Import failed: {e}")
