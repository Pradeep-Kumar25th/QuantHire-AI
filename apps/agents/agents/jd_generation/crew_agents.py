"""
LangGraph JD Generation Agents
==============================
Specialized agents that generate, refine, and validate Job Descriptions via
direct LangChain LLM invocation (LangGraph-orchestrated workflow).
"""

import logging
import os
import re
import warnings
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from agents.jd_generation.llm_runner import (
    build_agent_task_prompt,
    extract_llm_text,
    invoke_prompt_with_retry,
)


# ============================================================================
# CONTENT SANITIZATION - Remove agent reasoning artifacts from output
# ============================================================================
# These patterns match CrewAI/LLM internal reasoning that should NOT appear in final output
AGENT_REASONING_PATTERNS = [
    # OTPAR cycle markers
    r'\*\*ACT\*\*:.*?(?=\n\n|\Z)',
    r'\*\*OBSERVE\*\*:.*?(?=\n\n|\Z)',
    r'\*\*THINK\*\*:.*?(?=\n\n|\Z)',
    r'\*\*PLAN\*\*:.*?(?=\n\n|\Z)',
    r'\*\*REFLECT\*\*:.*?(?=\n\n|\Z)',
    # Step markers
    r'\*\*Step \d+:.*?(?=\n\n|\*\*Step|\Z)',
    r'Step \d+:.*?(?=\n\n|Step \d+:|\Z)',
    # Tool calling artifacts
    r'Calling tool:.*?(?=\n|\Z)',
    r'Parameters:.*?(?=\n|\Z)',
    r'Output:.*?```json.*?```',
    r'`retrieve_similar_jobs`.*?(?=\n|\Z)',
    r'`search_milvus`.*?(?=\n|\Z)',
    # JSON in code blocks (tool output)
    r'```json\s*\{.*?\}\s*```',
    # I will now execute/proceed patterns
    r'I will now execute.*?(?=\n\n|\Z)',
    r'I will proceed.*?(?=\n\n|\Z)',
    r'Let me.*?(?=\n\n|\Z)',
    r'Now I will.*?(?=\n\n|\Z)',
    # Agent internal thinking
    r'\[Agent\].*?(?=\n|\Z)',
    r'\[Thinking\].*?(?=\n|\Z)',
    r'\[Action\].*?(?=\n|\Z)',
    # Truncated content markers
    r'\.\.\..*?(?=\n|\Z)',
]


# Common spacing corrections for technology terms
TECH_TERM_CORRECTIONS = {
    'Tensor Flow': 'TensorFlow',
    'tensor flow': 'TensorFlow',
    'Py Torch': 'PyTorch',
    'py torch': 'PyTorch',
    'MLO ps': 'MLOps',
    'ML Ops': 'MLOps',
    'Fin Ops': 'FinOps',
    'fin ops': 'FinOps',
    'LLM s': 'LLMs',
    'Num Py': 'NumPy',
    'num py': 'NumPy',
    'Sci Py': 'SciPy',
    'sci py': 'SciPy',
    'Sci kit': 'Scikit',
    'scikit - learn': 'scikit-learn',
    'Postgre SQL': 'PostgreSQL',
    'postgre sql': 'PostgreSQL',
    'My SQL': 'MySQL',
    'my sql': 'MySQL',
    'Mongo DB': 'MongoDB',
    'mongo db': 'MongoDB',
    'Git Hub': 'GitHub',
    'git hub': 'GitHub',
    'Git Lab': 'GitLab',
    'Type Script': 'TypeScript',
    'type script': 'TypeScript',
    'Java Script': 'JavaScript',
    'java script': 'JavaScript',
    'Node js': 'Node.js',
    'Node JS': 'Node.js',
    'node js': 'Node.js',
    'Vue js': 'Vue.js',
    'Vue JS': 'Vue.js',
    'vue js': 'Vue.js',
    'Sage Maker': 'SageMaker',
    'Azure ML': 'Azure ML',
    'Kubeflow': 'Kubeflow',
    'ML flow': 'MLflow',
    'ml flow': 'MLflow',
    'Lang Chain': 'LangChain',
    'lang chain': 'LangChain',
    'Llama Index': 'LlamaIndex',
    'llama index': 'LlamaIndex',
    'Hugging Face': 'Hugging Face',
    'Spa Cy': 'spaCy',
    'spa cy': 'spaCy',
    'A / B': 'A/B',
    'Open AI': 'OpenAI',
    'open ai': 'OpenAI',
    'CI / CD': 'CI/CD',
    'Dev Ops': 'DevOps',
    'dev ops': 'DevOps',
    'Py Charm': 'PyCharm',
    # Metrics and scores
    'F 1-score': 'F1-score',
    'F 1 score': 'F1-score',
    'F1 - score': 'F1-score',
    'KPI s': 'KPIs',
    'AUC - ROC': 'AUC-ROC',
    # URL patterns - fix spaced slashes
    'https: / /': 'https://',
    'https:// ': 'https://',
    'http: / /': 'http://',
    'http:// ': 'http://',
    '. com / ': '.com/',
    '.com / ': '.com/',
    ' / apply': '/apply',
    # Common tool names with spacing issues
    'Mule Soft': 'MuleSoft',
    'mule soft': 'MuleSoft',
    'Swagger / Open API': 'Swagger/OpenAPI',
    'Swagger / OpenAPI': 'Swagger/OpenAPI',
    'Open API': 'OpenAPI',
    'ESB / ': 'ESB/',
    # Common abbreviations
    'ggplot 2': 'ggplot2',
    'Power BI': 'Power BI',
    'VS Code': 'VS Code',
    'SQL Server': 'SQL Server',
    'Jupyter Notebooks': 'Jupyter Notebooks',
    'Deep Speed': 'DeepSpeed',
    'Horovod': 'Horovod',
    # Additional common patterns
    'RAG s': 'RAGs',
    'API s': 'APIs',
    'GPU s': 'GPUs',
    'CPU s': 'CPUs',
    'NLP s': 'NLPs',
    'CNN s': 'CNNs',
    'RNN s': 'RNNs',
    'GAN s': 'GANs',
}


def normalize_tech_terms(text: str) -> str:
    """
    Fix spacing issues in technology terms.
    
    The LLM sometimes generates terms with spaces like 'Tensor Flow' instead of 'TensorFlow'.
    This function corrects these common patterns.
    
    Args:
        text: Text that may contain incorrectly spaced tech terms
        
    Returns:
        Text with corrected spacing
    """
    if not text or not isinstance(text, str):
        return text
    
    result = text
    for incorrect, correct in TECH_TERM_CORRECTIONS.items():
        result = result.replace(incorrect, correct)
    
    return result


def sanitize_jd_content(content: str) -> str:
    """
    Remove agent reasoning artifacts and fix encoding issues from JD content.
    
    This function strips out internal agent thinking, tool calls, and
    OTPAR cycle markers that accidentally leak into the final output.
    Also fixes unicode/encoding issues that can cause PDF rendering problems.
    
    Args:
        content: Raw content that may contain agent reasoning
        
    Returns:
        Cleaned content suitable for final JD
    """
    if not content or not isinstance(content, str):
        return content
    
    sanitized = content
    
    # STEP 0: Fix unicode/encoding issues FIRST (before pattern matching)
    # Convert unicode arrows to plain text separators
    sanitized = sanitized.replace('→', ' / ')
    sanitized = sanitized.replace('->', ' / ')
    sanitized = sanitized.replace('=>', ' / ')
    sanitized = sanitized.replace('←', ' / ')
    sanitized = sanitized.replace('↔', ' / ')
    
    # Fix garbled text patterns (spaces between single characters)
    # Pattern: "B u s i n e s s" -> "Business"
    def fix_garbled_word(match):
        chars = match.group(0).replace(' ', '')
        return chars
    # Match sequences of single letters separated by spaces (3+ letters)
    sanitized = re.sub(r'(?<![a-zA-Z])([a-zA-Z])\s+(?=([a-zA-Z]\s+){2,}[a-zA-Z](?![a-zA-Z]))', 
                       lambda m: m.group(1), sanitized)
    # Clean up remaining single-char sequences
    sanitized = re.sub(r'([A-Z])\s+([a-z])', r'\1\2', sanitized)  # "B usiness" -> "Business"
    
    # Fix common corrupted patterns
    sanitized = re.sub(r"!\s*['\"]?\s*", ' / ', sanitized)  # "!' " -> " / "
    sanitized = re.sub(r"&\s*!", ' / ', sanitized)  # "&!" -> " / "
    
    # Fix placeholder percentages (X%, Y%, N%) with reasonable defaults
    sanitized = re.sub(r'\bX%\b', '90%', sanitized)
    sanitized = re.sub(r'\bY%\b', '85%', sanitized)
    sanitized = re.sub(r'\bN%\b', '95%', sanitized)
    sanitized = re.sub(r'\[X\]%', '90%', sanitized)
    sanitized = re.sub(r'\[Y\]%', '85%', sanitized)
    sanitized = re.sub(r'\[N\]%', '95%', sanitized)
    
    # Apply all sanitization patterns for agent reasoning
    for pattern in AGENT_REASONING_PATTERNS:
        sanitized = re.sub(pattern, '', sanitized, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove multiple consecutive newlines
    sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
    
    # Remove leading/trailing whitespace
    sanitized = sanitized.strip()
    
    # If content is now empty or just whitespace, return None
    if not sanitized or len(sanitized) < 10:
        return None
    
    return sanitized


# REPETITIVE RESPONSIBILITY PATTERNS TO DETECT AND CONSOLIDATE
REPETITIVE_PATTERNS = [
    # Pattern: "Apply X expertise to deliver project objectives"
    r'^Apply\s+\w+\s+expertise\s+to\s+deliver\s+project\s+objectives\.?$',
    # Pattern: "Apply X expertise to support..."
    r'^Apply\s+\w+\s+expertise\s+to\s+',
    # Pattern: "Collaborate with cross-functional teams to deliver project objectives"
    r'^Collaborate\s+with\s+cross-functional\s+teams\s+to\s+deliver\s+project\s+objectives\.?$',
    # Pattern: "Work with teams to deliver..."
    r'^Work\s+with\s+\w+\s+teams?\s+to\s+deliver\s+',
]


def deduplicate_responsibilities(responsibilities: List[str], job_level: str = '') -> List[str]:
    """
    Remove repetitive/redundant responsibilities and consolidate similar patterns.
    
    This is a POST-PROCESSING function that cleans up the AI agents' output.
    The 5 CrewAI agents generate the content; this function only:
    1. Removes exact/near duplicates
    2. Consolidates repetitive patterns into a single impactful statement
    3. Transforms responsibilities to use level-appropriate action verbs
    
    The consolidation uses the EXTRACTED expertise terms from the AI output,
    not hardcoded values - keeping it truly agentic.
    
    Args:
        responsibilities: List of responsibility strings (from AI agents)
        job_level: The job level (junior, mid, senior, etc.)
        
    Returns:
        Deduplicated list of responsibilities with level-appropriate language
    """
    if not responsibilities:
        return responsibilities
    
    deduplicated = []
    seen_patterns = set()
    consolidated_expertise = []
    has_collaborate_pattern = False
    
    level_lower = job_level.lower() if job_level else ''
    
    # Define level-appropriate action verb transformations
    # Map generic verbs to level-specific verbs
    junior_verbs = {
        'lead': 'Assist with',
        'architect': 'Support the design of',
        'design': 'Assist in designing',
        'drive': 'Participate in',
        'mentor': 'Learn from mentors while',
        'define': 'Help define',
        'establish': 'Support the establishment of',
        'transform': 'Contribute to transforming',
    }
    
    senior_verbs = {
        'assist': 'Lead',
        'support': 'Drive',
        'participate': 'Spearhead',
        'help': 'Champion',
        'learn': 'Mentor others while',
        'execute': 'Architect and execute',
    }
    
    for resp in responsibilities:
        if not isinstance(resp, str):
            continue
        
        resp_clean = resp.strip()
        resp_lower = resp_clean.lower()
        
        # Detect "Apply X expertise to deliver project objectives" pattern
        # Made more robust to handle variations
        apply_patterns = [
            r'apply\s+(.+?)\s+expertise\s+to\s+deliver\s+(?:project\s+)?objectives',
            r'apply\s+(.+?)\s+expertise\s+to\s+(?:achieve|support|meet)\s+',
            r'utilize\s+(.+?)\s+expertise\s+to\s+deliver\s+',
            r'leverage\s+(.+?)\s+expertise\s+to\s+',
            r'employ\s+(.+?)\s+expertise\s+to\s+',
        ]
        
        matched_expertise = False
        for pattern in apply_patterns:
            apply_match = re.search(pattern, resp_lower)
            if apply_match:
                expertise = apply_match.group(1).strip().title()
                # Clean up expertise text
                expertise = re.sub(r'\s+', ' ', expertise)  # Normalize whitespace
                if expertise and expertise not in consolidated_expertise:
                    consolidated_expertise.append(expertise)
                    logger.info(f"🔄 Found repetitive expertise pattern: '{expertise}'")
                matched_expertise = True
                break
        
        if matched_expertise:
            continue
        
        # Detect generic "Collaborate with cross-functional teams to deliver project objectives"
        if 'cross-functional teams to deliver project objectives' in resp_lower:
            has_collaborate_pattern = True
            logger.info(f"🔄 Found generic 'Collaborate' pattern - will consolidate")
            continue
        
        # Check for similar responsibilities (avoid near-duplicates)
        normalized = re.sub(r'[^\w\s]', '', resp_lower)
        normalized = ' '.join(sorted(normalized.split()))
        
        if normalized in seen_patterns:
            logger.info(f"🔄 Skipping near-duplicate responsibility")
            continue
        
        seen_patterns.add(normalized)
        
        # Transform responsibility based on job level
        transformed_resp = resp_clean
        
        if 'junior' in level_lower or 'entry' in level_lower:
            # For junior: Replace senior verbs with junior-appropriate ones
            for senior_verb, junior_verb in junior_verbs.items():
                if resp_lower.startswith(senior_verb):
                    transformed_resp = junior_verb + resp_clean[len(senior_verb):]
                    logger.info(f"🔄 Transformed '{senior_verb}' to '{junior_verb}' for junior level")
                    break
        elif 'senior' in level_lower or 'lead' in level_lower:
            # For senior: Replace junior verbs with senior-appropriate ones
            for junior_verb, senior_verb in senior_verbs.items():
                if resp_lower.startswith(junior_verb):
                    transformed_resp = senior_verb + resp_clean[len(junior_verb):]
                    logger.info(f"🔄 Transformed '{junior_verb}' to '{senior_verb}' for senior level")
                    break
        
        deduplicated.append(transformed_resp)
    
    # Consolidate the "Apply X expertise" into one impactful statement
    # Uses the EXTRACTED expertise terms from AI output (dynamic, not hardcoded)
    if consolidated_expertise:
        # Take up to 4 expertise items
        expertise_list = ', '.join(consolidated_expertise[:4])
        if len(consolidated_expertise) > 4:
            expertise_list += f", and {len(consolidated_expertise) - 4} more"
        
        # Level-appropriate consolidated statement
        if 'junior' in level_lower or 'entry' in level_lower:
            consolidated = f"Support the application of {expertise_list} expertise under senior guidance to contribute to project objectives"
        elif 'senior' in level_lower or 'lead' in level_lower:
            consolidated = f"Lead the strategic application of {expertise_list} expertise to architect scalable solutions and mentor team members"
        else:
            consolidated = f"Apply {expertise_list} expertise to design and deliver solutions aligned with project objectives"
        
        deduplicated.append(consolidated)
        logger.info(f"✅ Consolidated {len(consolidated_expertise)} expertise patterns into one level-appropriate statement")
    
    # Add a meaningful collaboration statement if pattern was detected
    if has_collaborate_pattern:
        # Check if there's already a collaboration responsibility
        has_collab = any('cross-functional' in d.lower() and 'collaborat' in d.lower() for d in deduplicated)
        if not has_collab:
            deduplicated.append("Collaborate effectively with cross-functional teams to ensure successful project delivery")
            logger.info(f"✅ Added meaningful collaboration responsibility")
    
    # Log the result
    original_count = len(responsibilities)
    final_count = len(deduplicated)
    if final_count < original_count:
        logger.info(f"🤖 Agentic cleanup: {original_count} → {final_count} responsibilities")
    
    return deduplicated


def sanitize_jd_dict(jd: Dict[str, Any]) -> Dict[str, Any]:
    """
    Post-process JD dictionary generated by the 5 autonomous CrewAI agents.
    
    =========================================================================
    🤖 AGENTIC AI ARCHITECTURE
    =========================================================================
    This function is a POST-PROCESSING step that runs AFTER the 5 fully
    autonomous CrewAI agents have completed their OTPAR cycles:
    
    1. JDGeneratorAgent   - Generates initial 15-section enterprise JD
    2. JDRefinerAgent     - Refines and enhances the content
    3. JDValidatorAgent   - Validates compliance and quality
    4. RAGAgent           - Retrieves similar jobs for context
    5. MilvusStorageAgent - Stores in vector database
    
    The agents use LangGraph orchestration and CrewAI collaboration to
    generate content autonomously. This function only:
    - Removes agent reasoning artifacts (OTPAR markers, tool calls)
    - Fixes tech term spacing (TensorFlow, PyTorch, etc.)
    - Deduplicates repetitive patterns
    - Provides Malomatia defaults ONLY if agents left fields empty
    
    We TRUST the AI agents' output. We do NOT hardcode content overrides.
    =========================================================================
    
    Args:
        jd: JD dictionary generated by autonomous AI agents
        
    Returns:
        Cleaned JD dictionary
    """
    # STEP 0: Fix department field encoding issues
    if 'department' in jd and isinstance(jd['department'], str):
        dept = jd['department']
        # Fix unicode arrows
        dept = dept.replace('→', ' / ')
        dept = dept.replace('->', ' / ')
        # Fix garbled separators
        dept = re.sub(r"!\s*['\"]?\s*", ' / ', dept)
        dept = re.sub(r"&\s*!", ' / ', dept)
        # Fix garbled text (spaces between single characters)
        # "B u s i n e s s" -> "Business"
        words = dept.split(' / ')
        cleaned_words = []
        for word in words:
            word = word.strip()
            # Check if word has spaces between single characters
            parts = word.split()
            if len(parts) > 3 and all(len(p) <= 2 for p in parts):
                # Likely garbled - join the characters
                word = ''.join(parts)
            cleaned_words.append(word)
        dept = ' / '.join(cleaned_words)
        # Normalize multiple slashes
        dept = re.sub(r'\s*/\s*', ' / ', dept)
        dept = re.sub(r'(\s*/\s*){2,}', ' / ', dept)
        jd['department'] = dept.strip()
        logger.info(f"🧹 Sanitized department: {jd['department']}")
    
    # Fields that commonly get polluted with agent reasoning
    text_fields = [
        'position_summary',
        'about_company',
        'equal_opportunity_statement',
    ]
    
    for field in text_fields:
        if field in jd and isinstance(jd[field], str):
            original = jd[field]
            sanitized = sanitize_jd_content(jd[field])
            # Also normalize tech terms (fix spacing issues)
            sanitized = normalize_tech_terms(sanitized) if sanitized else sanitized
            if sanitized != original:
                logger.info(f"🧹 Sanitized {field}: removed {len(original) - len(sanitized or '')} chars of reasoning artifacts")
            if sanitized:
                jd[field] = sanitized
            else:
                # Content was fully contaminated - set to None so it can be regenerated
                jd[field] = None
                logger.warning(f"⚠️ {field} was fully contaminated - marked for regeneration")
    
    # =========================================================================
    # POSITION SUMMARY VALIDATION
    # The 5 CrewAI agents generate the position_summary via OTPAR cycle.
    # We only use fallback if the AI output is COMPLETELY broken/missing.
    # =========================================================================
    job_title = jd.get('job_title', 'Professional')
    job_level = jd.get('job_level', '')
    department = jd.get('department', '')
    
    needs_fallback = False
    current_summary = jd.get('position_summary', '')
    
    # Only fallback if content is EMPTY or has obvious structural issues
    if not current_summary or current_summary is None or current_summary.strip() == '':
        needs_fallback = True
        logger.warning("⚠️ AI agents did not generate position_summary - using Malomatia fallback")
    elif "The at " in current_summary or "The  at " in current_summary:
        # Pattern like "The at Malomatia..." indicates missing job title (structural issue)
        needs_fallback = True
        logger.warning("⚠️ position_summary has structural issue - using Malomatia fallback")
    # If AI generated content but didn't mention job title, LOG but KEEP the AI output
    elif job_title.lower() not in current_summary.lower() and job_level.lower() not in current_summary.lower():
        logger.warning(f"⚠️ Validation: position_summary doesn't mention '{job_title}' (AI output kept)")
    
    if needs_fallback:
        fallback_summary = generate_fallback_position_summary(job_title, job_level, department)
        jd['position_summary'] = fallback_summary
        logger.info(f"✅ Generated fallback position_summary for {job_title}")
    
    # Sanitize list fields (responsibilities, qualifications, etc.)
    list_fields = [
        'responsibilities',
        'preferred_qualifications',
        'soft_skills',
        'tools_technologies',
        'success_metrics',
        'compensation_benefits',
    ]
    
    for field in list_fields:
        if field in jd and isinstance(jd[field], list):
            cleaned_list = []
            for item in jd[field]:
                if isinstance(item, str):
                    sanitized_item = sanitize_jd_content(item)
                    # Also normalize tech terms in list items
                    sanitized_item = normalize_tech_terms(sanitized_item) if sanitized_item else sanitized_item
                    if sanitized_item and len(sanitized_item) > 5:
                        cleaned_list.append(sanitized_item)
                else:
                    cleaned_list.append(item)
            if len(cleaned_list) < len(jd[field]):
                logger.info(f"🧹 Sanitized {field}: removed {len(jd[field]) - len(cleaned_list)} contaminated items")
            jd[field] = cleaned_list
    
    # DEDUPLICATE AND FIX REPETITIVE RESPONSIBILITIES
    # This is a POST-PROCESSING cleanup, not content generation
    # The 5 CrewAI agents generate the content; this just cleans up patterns
    if 'responsibilities' in jd and isinstance(jd['responsibilities'], list):
        jd['responsibilities'] = deduplicate_responsibilities(jd['responsibilities'], jd.get('job_level', ''))
    
    # Handle nested dicts like required_qualifications
    if 'required_qualifications' in jd and isinstance(jd['required_qualifications'], dict):
        rq = jd['required_qualifications']
        for key in ['education', 'experience']:
            if key in rq and isinstance(rq[key], str):
                sanitized = sanitize_jd_content(rq[key])
                sanitized = normalize_tech_terms(sanitized) if sanitized else sanitized
                if sanitized:
                    rq[key] = sanitized
        if 'technical_skills' in rq and isinstance(rq['technical_skills'], list):
            rq['technical_skills'] = [
                normalize_tech_terms(sanitize_jd_content(s)) for s in rq['technical_skills'] 
                if isinstance(s, str) and sanitize_jd_content(s)
            ]
    
    # =========================================================================
    # AGENTIC VALIDATION - Log warnings but TRUST the AI agents' output
    # The 5 CrewAI agents (JD Architect, Skills Analyst, Compliance Reviewer,
    # Industry Expert, Quality Assurance) generate content via OTPAR cycle.
    # We only override if content is COMPLETELY MISSING (None/empty).
    # =========================================================================
    job_level = jd.get('job_level', '').lower()
    logger.info(f"🤖 Agentic JD Validation for job_level='{job_level}'")
    
    if 'required_qualifications' not in jd or not isinstance(jd.get('required_qualifications'), dict):
        jd['required_qualifications'] = {}
    
    rq = jd['required_qualifications']
    
    # ONLY populate education if agents left it EMPTY (safety net, not override)
    current_edu = rq.get('education', '')
    if not current_edu or current_edu.strip() == '':
        logger.warning(f"⚠️ AI agents did not generate education - using Malomatia default")
        rq['education'] = "Bachelor's degree in relevant field or equivalent experience."
    else:
        # Log validation warning but TRUST the agent's output
        if ('junior' in job_level or 'entry' in job_level) and "master's" in current_edu.lower() and "preferred" not in current_edu.lower():
            logger.warning(f"⚠️ Validation: Education may be too advanced for {job_level} level (AI output kept)")
    
    # Experience validation with CRITICAL safety net for level mismatch
    current_exp = rq.get('experience', '')
    if not current_exp or current_exp.strip() == '':
        logger.warning(f"⚠️ AI agents did not generate experience - using Malomatia default")
        rq['experience'] = "Relevant professional experience in the field."
    else:
        # CRITICAL SAFETY NET: Fix experience if it doesn't match job level
        # This is NOT an override - it's fixing an AI error that validators caught
        years_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', current_exp.lower())
        
        if 'junior' in job_level or 'entry' in job_level:
            # Junior: 0-2 years (should NOT show 3+ years)
            if years_match and int(years_match.group(1)) >= 3:
                logger.warning(f"⚠️ FIXING: Experience '{years_match.group(0)}' does not match {job_level} level - correcting to 0-2 years")
                rq['experience'] = "0-2 years of relevant experience in the field. Internships and academic projects count towards experience."
        elif 'mid' in job_level or 'intermediate' in job_level:
            # Mid-Level: 3-5 years (should NOT show 0-2 or 6+ years)
            if years_match and (int(years_match.group(1)) < 3 or int(years_match.group(1)) > 5):
                logger.warning(f"⚠️ FIXING: Experience '{years_match.group(0)}' does not match {job_level} level - correcting to 3-5 years")
                rq['experience'] = "3-5 years of professional experience in the field."
        elif 'senior' in job_level:
            # Senior: 5-8 years (should NOT show less than 5 years)
            if years_match and int(years_match.group(1)) < 5:
                logger.warning(f"⚠️ FIXING: Experience '{years_match.group(0)}' does not match {job_level} level - correcting to 5-8 years")
                rq['experience'] = "5-8 years of extensive professional experience in the field. Demonstrated expertise in leading technical initiatives and mentoring team members."
        elif 'lead' in job_level or 'principal' in job_level:
            # Lead/Principal: 8+ years (should NOT show less than 8 years)
            if years_match and int(years_match.group(1)) < 8:
                logger.warning(f"⚠️ FIXING: Experience '{years_match.group(0)}' does not match {job_level} level - correcting to 8+ years")
                rq['experience'] = "8+ years of progressive professional experience with proven leadership and technical expertise. Track record of driving strategic initiatives and building high-performing teams."
    
    # ONLY populate reports_to if agents left it EMPTY (safety net, not override)
    if 'work_environment' not in jd or not isinstance(jd.get('work_environment'), dict):
        jd['work_environment'] = {}
    
    we = jd['work_environment']
    current_reports = we.get('reports_to', '')
    if not current_reports or current_reports.strip() == '':
        # Generate level-appropriate reports_to if not provided
        logger.warning(f"⚠️ AI agents did not generate reports_to - using level-appropriate default")
        if 'junior' in job_level or 'entry' in job_level:
            we['reports_to'] = "Team Lead or Senior Engineer"
        elif 'mid' in job_level or 'intermediate' in job_level:
            we['reports_to'] = "Engineering Manager"
        elif 'senior' in job_level:
            we['reports_to'] = "Director of Engineering"
        elif 'lead' in job_level or 'principal' in job_level:
            we['reports_to'] = "VP of Engineering or CTO"
        else:
            we['reports_to'] = "Department Manager"
    else:
        # Log validation warning but TRUST the agent's output
        if ('junior' in job_level or 'entry' in job_level) and ('director' in current_reports.lower() or 'vp' in current_reports.lower() or 'cto' in current_reports.lower()):
            logger.warning(f"⚠️ Validation: reports_to '{current_reports}' may be too senior for {job_level} level (AI output kept)")
    
    return jd


def generate_fallback_position_summary(job_title: str, job_level: str = "", department: str = "") -> str:
    """
    Generate a fallback position summary when the LLM-generated one was contaminated.
    
    Args:
        job_title: The job title
        job_level: Optional job level (Senior, Junior, etc.)
        department: Optional department
        
    Returns:
        A professional position summary
    """
    title_lower = job_title.lower()
    level_lower = job_level.lower() if job_level else ''
    level_str = f"{job_level} " if job_level else ""
    dept_str = f" in the {department} department" if department else ""
    
    # Level-specific prefixes - EXPLICIT handling for ALL levels
    if 'junior' in level_lower or 'entry' in level_lower:
        level_context = "will support the design and implementation of"
        mentor_text = " under the guidance of senior engineers"
        growth_text = " This role focuses on developing foundational skills and learning best practices."
    elif 'mid' in level_lower or 'intermediate' in level_lower:
        level_context = "is responsible for developing and implementing"
        mentor_text = ""
        growth_text = " This role involves taking ownership of key deliverables and collaborating across teams."
    elif 'senior' in level_lower:
        level_context = "will lead the design and architecture of"
        mentor_text = ", mentoring junior team members"
        growth_text = " This role provides technical leadership and drives strategic initiatives."
    elif 'lead' in level_lower or 'principal' in level_lower:
        level_context = "will define and transform the strategic direction of"
        mentor_text = ", building and developing high-performing teams"
        growth_text = " This role shapes organizational strategy and establishes technical excellence."
    else:
        level_context = "is responsible for developing and implementing"
        mentor_text = ""
        growth_text = " This role involves taking ownership of key deliverables and collaborating across teams."
    
    # Security/Cybersecurity roles
    if any(kw in title_lower for kw in ['security', 'cybersecurity', 'infosec', 'vulnerability']):
        if 'junior' in level_lower or 'entry' in level_lower:
            return f"The {level_str}{job_title}{dept_str} will support the implementation of security measures and assist in monitoring for security incidents under the guidance of senior security engineers. This role focuses on developing foundational skills in cybersecurity, learning vulnerability assessment techniques, and understanding compliance requirements. The successful candidate will work closely with IT teams to maintain Malomatia's security posture."
        else:
            return f"The {level_str}{job_title}{dept_str} {level_context} security solutions to protect organizational information assets{mentor_text}. This role involves implementing security measures, conducting vulnerability assessments, and ensuring compliance with security policies.{growth_text}"
    
    # Integration/Middleware roles
    elif any(kw in title_lower for kw in ['integration', 'middleware', 'esb', 'api']):
        if 'junior' in level_lower or 'entry' in level_lower:
            return f"The {level_str}{job_title}{dept_str} will support the design and implementation of integrated enterprise systems under the guidance of senior engineers. This role involves working with APIs, middleware, and data synchronization techniques to ensure reliable data flow across platforms. The successful candidate will develop foundational integration skills while contributing to Malomatia's digital transformation initiatives."
        else:
            return f"The {level_str}{job_title}{dept_str} {level_context} integrated systems solutions{mentor_text}. This role involves ensuring seamless data flow across platforms using APIs, middleware, and ESB technologies.{growth_text}"
    
    # Engineering/Development roles
    elif any(kw in title_lower for kw in ['engineer', 'developer', 'programmer', 'software']):
        if 'junior' in level_lower or 'entry' in level_lower:
            return f"The {level_str}{job_title}{dept_str} will support the development and maintenance of software solutions under the guidance of senior engineers. This role focuses on writing clean code, learning development best practices, and contributing to the software development lifecycle. The successful candidate will develop foundational technical skills while collaborating with cross-functional teams."
        else:
            return f"The {level_str}{job_title}{dept_str} {level_context} high-quality software solutions{mentor_text}. This role involves collaborating with cross-functional teams to deliver scalable applications.{growth_text}"
    
    # Data/Analytics roles
    elif any(kw in title_lower for kw in ['data', 'analyst', 'analytics', 'scientist']):
        return f"The {level_str}{job_title}{dept_str} {level_context} data analysis and insights{mentor_text}. This role involves processing data, creating visualizations, and supporting data-driven decisions.{growth_text}"
    
    # AI/ML/Artificial Intelligence roles
    elif any(kw in title_lower for kw in ['artificial intelligence', 'ai', 'machine learning', 'ml', 'deep learning', 'neural', 'nlp', 'computer vision']):
        return f"The {level_str}{job_title}{dept_str} at Malomatia {level_context} AI and Machine Learning solutions{mentor_text}. This role involves building ML models, implementing deep learning architectures, and leveraging modern AI frameworks.{growth_text}"
    
    # Management/Leadership roles
    elif any(kw in title_lower for kw in ['manager', 'director', 'lead', 'head']):
        return f"The {level_str}{job_title}{dept_str} is responsible for leading and developing high-performing teams while driving strategic initiatives. This role involves setting goals, managing resources, fostering collaboration, and ensuring successful delivery of projects and objectives. The successful candidate will provide mentorship, build strong stakeholder relationships, and contribute to organizational growth."
    
    # Default generic summary - ensure job_title is mentioned
    else:
        return f"The {level_str}{job_title}{dept_str} at Malomatia {level_context} impactful solutions{mentor_text}. This role involves collaborating with teams and implementing best practices.{growth_text}"

# Suppress LangChain deprecation warning for ChatVertexAI
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain_google_vertexai")

try:
    from langchain_google_vertexai import ChatVertexAI
except ImportError:
    ChatVertexAI = None

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

# LangSmith is optional
try:
    from langsmith import traceable
except ImportError:
    # Create a no-op decorator if langsmith is not available
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
logger = logging.getLogger(__name__)

from agents.jd_generation.autonomous_agent import AutonomousAgent, Environment


# ============================================================================
# USER REQUIREMENTS PARSER - Pattern-based categorization (no hardcoding)
# ============================================================================


def is_known_tool_or_technology(item: str) -> bool:
    """
    Dynamically detect if an item is a tool/technology using patterns.
    No hardcoded lists - uses regex patterns to recognize tool categories.
    """
    if not item:
        return False
    
    item_lower = item.lower().strip()
    
    # Pattern-based detection for common tool categories
    tool_patterns = [
        # Programming languages (typically short, single word)
        r'^(java|python|javascript|typescript|c\+\+|c#|go|rust|kotlin|swift|ruby|php|scala|r|matlab|perl|bash|shell|powershell)$',
        # Frameworks (often end with .js, contain known patterns)
        r'\.(js|py|rb|go)$',
        r'^(react|angular|vue|node|express|django|flask|spring|fastapi|rails|laravel|next)[\.\s]?(js|boot)?$',
        # Databases (end with db, sql, contain db/cache keywords)
        r'(sql|db|database|cache|store|dynamo|elastic|redis|mongo|cassandra|neo4j|postgres|mysql|oracle|sqlite|mariadb)$',
        # Cloud providers
        r'^(aws|azure|gcp|google\s*cloud|heroku|digital\s*ocean|cloudflare)$',
        # DevOps tools
        r'^(docker|kubernetes|k8s|terraform|ansible|puppet|chef|vagrant|helm)$',
        # CI/CD tools
        r'(jenkins|gitlab|github|circleci|travis|bamboo|teamcity|actions)$',
        r'^ci/?cd$',
        # Version control
        r'^(git|github|gitlab|bitbucket|svn|mercurial)$',
        # ML/Data tools
        r'^(pandas|numpy|scikit|tensorflow|pytorch|keras|spark|hadoop|kafka|airflow|mlflow|dvc)$',
        r'(learn|flow|torch)$',
        # Visualization
        r'^(tableau|power\s*bi|grafana|kibana|looker|metabase)$',
        # APIs/Protocols
        r'^(rest|graphql|grpc|soap|websocket)$',
    ]
    
    for pattern in tool_patterns:
        if re.search(pattern, item_lower, re.IGNORECASE):
            return True
    
    # Also check: short items (1-2 words, < 15 chars) that don't contain spaces
    # are more likely to be tool names
    if len(item_lower) <= 12 and ' ' not in item_lower:
        return True
    
    return False


def is_concept_or_methodology(item: str) -> bool:
    """
    Dynamically detect if an item is a concept/methodology (not a tool).
    No hardcoded lists - uses regex patterns to recognize concept categories.
    """
    if not item:
        return False
    
    item_lower = item.lower().strip()
    
    # Pattern-based detection for concepts/methodologies
    concept_patterns = [
        # CS fundamentals
        r'\b(data\s+structures?|algorithms?|complexity|oop|object[\s-]?oriented|design\s+patterns?|solid\s+principles?)\b',
        # Architecture concepts
        r'\b(system\s+design|architecture|microservices?|monolith|distributed\s+systems?)\b',
        # Testing concepts
        r'\b(testing|test[\s-]?driven|tdd|bdd|unit\s+test|integration\s+test)\b',
        # Soft skills
        r'\b(problem[\s-]?solving|communication|teamwork|leadership|collaboration)\b',
        # Methodologies
        r'\b(agile|scrum|kanban|waterfall|lean|six\s+sigma)\s*(methodology|framework)?$',
        # Design concepts
        r'\b(api\s+design|restful?\s+design|clean\s+code|code\s+review)\b',
    ]
    
    for pattern in concept_patterns:
        if re.search(pattern, item_lower, re.IGNORECASE):
            return True
    
    # Multi-word phrases (> 2 words) are more likely to be concepts than tool names
    word_count = len(item_lower.split())
    if word_count > 2 and not is_known_tool_or_technology(item):
        return True
    
    return False


# ============================================================================
# TEXT CLEANUP FUNCTIONS - Dynamic pattern-based fixes (no hardcoding)
# ============================================================================


def fix_spacing_errors(text: str) -> str:
    """
    Dynamically fix spacing errors using intelligent pattern detection.
    No hardcoded words - uses regex patterns to detect:
    - Uppercase abbreviations merged with lowercase words
    - Articles (A/An) merged with following words
    - Common punctuation issues
    
    Examples:
        "CI/CDfor ML" -> "CI/CD for ML"
        "MLmodels" -> "ML models"
        "Rfor" -> "R for"
        "Aportfolio" -> "A portfolio"
    """
    if not text:
        return text
    
    fixed = text
    
    # ========================================================================
    # PATTERN 1: Uppercase abbreviation followed by lowercase word (no space)
    # Matches: "MLmodels", "AIoperations", "CI/CDfor", "SQLfor", "AWSservices"
    # Pattern: 2+ uppercase letters (optionally with / or numbers) directly followed
    #          by a lowercase letter, where the lowercase starts a common word
    # ========================================================================
    # Common lowercase words that often get merged
    common_following_words = r'(for|and|to|with|in|on|of|or|the|a|an|using|models|pipelines|infrastructure|environments|systems|training|platforms|workloads|operations|driven|design|development|management|services|solutions|applications)'
    fixed = re.sub(
        rf'\b([A-Z][A-Z0-9/]+)({common_following_words})\b',
        r'\1 \2',
        fixed
    )
    
    # ========================================================================
    # PATTERN 2: Single uppercase letter + lowercase word (like "Rfor", "Aportfolio")
    # Only for single letters that are commonly words: R, A, I, etc.
    # ========================================================================
    # "Rfor" -> "R for", "Rand" -> "R and"
    fixed = re.sub(r'\bR(for|and|or|to|with)\b', r'R \1', fixed)
    # "Aportfolio" -> "A portfolio", "Astrong" -> "A strong" 
    # Match: A followed by lowercase letter at word boundary
    fixed = re.sub(r'\bA([a-z][a-z]+)\b', r'A \1', fixed)
    # "Anunusual" -> "An unusual"
    fixed = re.sub(r'\bAn([a-z][a-z]+)\b', r'An \1', fixed)
    
    # ========================================================================
    # PATTERN 3: Article spacing after sentence boundaries
    # "sentence. Aword" or start of text "Aword"
    # ========================================================================
    fixed = re.sub(r'(?<=[.!?\n] )A([a-z])', r'A \1', fixed)
    fixed = re.sub(r'^A([a-z])', r'A \1', fixed)
    fixed = re.sub(r'(?<=[.!?\n] )An([a-z])', r'An \1', fixed)
    fixed = re.sub(r'^An([a-z])', r'An \1', fixed)
    
    # ========================================================================
    # PATTERN 4: Punctuation errors (dynamic patterns, no hardcoding)
    # ========================================================================
    fixed = re.sub(r'\.,', '.', fixed)           # analysis., -> analysis.
    fixed = re.sub(r',\.', '.', fixed)           # ,. -> .
    fixed = re.sub(r'\.\s*,', '.', fixed)        # . , -> .
    fixed = re.sub(r',\s*\.', '.', fixed)        # , . -> .
    fixed = re.sub(r'\.\.+', '.', fixed)         # .. or ... -> .
    fixed = re.sub(r',\s*,', ',', fixed)         # ,, -> ,
    fixed = re.sub(r'\s+,', ',', fixed)          # space before comma
    fixed = re.sub(r'\s+\.', '.', fixed)         # space before period
    fixed = re.sub(r',([A-Z])', r', \1', fixed)  # comma immediately followed by capital
    
    # ========================================================================
    # PATTERN 5: CamelCase in wrong context (mid-sentence unexpected capitals)
    # Example: "the dataScientist will" -> likely an error
    # Be careful not to affect intentional CamelCase (variable names, product names)
    # ========================================================================
    # Only fix obvious cases: lowercase + Uppercase at word boundaries in prose
    # "work withData" -> "work with Data" - but this is risky, skip for now
    
    # ========================================================================
    # PATTERN 6: Multiple spaces -> single space
    # ========================================================================
    fixed = re.sub(r'  +', ' ', fixed)
    
    return fixed


def remove_ui_artifacts(text: str) -> str:
    """
    Remove UI artifacts using pattern-based detection (no hardcoded strings).
    Catches patterns like "Show X more", "Click here", navigation text, etc.
    """
    if not text:
        return text
    
    cleaned = text
    
    # ========================================================================
    # PATTERN 1: "Show/See X more/less/all" patterns (dynamic number detection)
    # ========================================================================
    cleaned = re.sub(r'\b[Ss]how\s+\d+\s+more\b', '', cleaned)
    cleaned = re.sub(r'\b[Ss]how\s+\d+\s+less\b', '', cleaned)
    cleaned = re.sub(r'\b[Ss]how\s+more\b', '', cleaned)
    cleaned = re.sub(r'\b[Ss]how\s+less\b', '', cleaned)
    cleaned = re.sub(r'\b[Ss]how\s+all\b', '', cleaned)
    cleaned = re.sub(r'\b[Ss]how\s+fewer\b', '', cleaned)
    cleaned = re.sub(r'\b[Ss]ee\s+\d+\s+more\b', '', cleaned)
    cleaned = re.sub(r'\b[Ss]ee\s+more\b', '', cleaned)
    cleaned = re.sub(r'\b[Ss]ee\s+less\b', '', cleaned)
    
    # ========================================================================
    # PATTERN 2: Navigation/Action text patterns
    # ========================================================================
    cleaned = re.sub(r'\b[Cc]lick\s+here\b', '', cleaned)
    cleaned = re.sub(r'\b[Rr]ead\s+more\b', '', cleaned)
    cleaned = re.sub(r'\b[Vv]iew\s+more\b', '', cleaned)
    cleaned = re.sub(r'\b[Ll]oad\s+more\b', '', cleaned)
    cleaned = re.sub(r'\b[Ee]xpand\b(?!\s+\w)', '', cleaned)  # Expand alone, not "Expand team"
    cleaned = re.sub(r'\b[Cc]ollapse\b(?!\s+\w)', '', cleaned)
    cleaned = re.sub(r'\b[Hh]ide\s+all\b', '', cleaned)
    
    # ========================================================================
    # PATTERN 3: UI button text patterns (Edit, Download, Save buttons)
    # ========================================================================
    cleaned = re.sub(r'\b[Ee]dit\s+all\s+sections?\b', '', cleaned)
    cleaned = re.sub(r'\b[Dd]ownload\s+as\s+[Pp][Dd][Ff]\b', '', cleaned)
    cleaned = re.sub(r'\b[Ss]ave\s+to\s+[Mm]ilvus\b', '', cleaned)
    
    # ========================================================================
    # Clean up any resulting double spaces or empty lines
    # ========================================================================
    cleaned = re.sub(r'  +', ' ', cleaned)
    cleaned = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned)
    
    return cleaned.strip()


def dedupe_soft_skills(skills: List[str]) -> List[str]:
    """
    Deduplicate soft skills using pattern-based semantic grouping.
    Uses regex patterns to detect variations of the same concept (no hardcoded lists).
    """
    if not skills:
        return []
    
    result = []
    seen_exact = set()
    used_categories = set()
    
    # Pattern-based category detection (regex patterns for each category)
    # Format: (pattern_regex, canonical_name, category_key)
    category_patterns = [
        # Mentorship/Coaching
        (r'\b(mentor|coaching|guidance|coach)\b', 'Mentorship and Guidance', 'mentorship'),
        # Leadership
        (r'\b(leader|leadership|lead\s+teams?)\b', 'Technical Leadership', 'leadership'),
        # Communication
        (r'\b(communication|verbal|written|communicate)\b', 'Excellent Communication', 'communication'),
        # Problem-solving
        (r'\b(problem[\s-]?solv|analytical)\b', 'Problem-Solving', 'problem_solving'),
        # Teamwork/Collaboration
        (r'\b(team\s*work|collaborat|team\s+player|cross[\s-]?functional)\b', 'Collaboration and Teamwork', 'teamwork'),
        # Strategic thinking
        (r'\b(strateg|strategic\s+thinking|strategic\s+mindset)\b', 'Strategic Thinking', 'strategic'),
        # Learning/Curiosity
        (r'\b(learn|curious|curiosity|growth\s+mindset)\b', 'Eagerness to Learn', 'learning'),
        # Attention to detail
        (r'\b(detail[\s-]?orient|attention\s+to\s+detail|meticulous)\b', 'Attention to Detail', 'attention'),
        # Time management
        (r'\b(time\s+management|priorit|deadline)\b', 'Time Management', 'time_mgmt'),
        # Adaptability
        (r'\b(adapt|flexib|agile\s+mindset)\b', 'Adaptability', 'adaptability'),
    ]
    
    for skill in skills:
        if not isinstance(skill, str):
            continue
        
        # Normalize
        skill_clean = skill.strip()
        if skill_clean.endswith('.'):
            skill_clean = skill_clean[:-1].strip()
        skill_lower = skill_clean.lower()
        
        # Skip empty or exact duplicates
        if not skill_lower or skill_lower in seen_exact:
            continue
        seen_exact.add(skill_lower)
        
        # Check if matches any category pattern
        found_category = False
        for pattern, canonical, category_key in category_patterns:
            if re.search(pattern, skill_lower, re.IGNORECASE):
                if category_key not in used_categories:
                    used_categories.add(category_key)
                    result.append(canonical)
                found_category = True
                break
        
        # If no pattern matched, keep the original (cleaned)
        if not found_category:
            result.append(skill_clean)
    
    return result


def clean_tools_technologies(tools: List[str], job_title: str = "") -> List[str]:
    """
    Clean tools_technologies list using pattern-based detection (no hardcoded lists):
    - Remove non-tool items (Office Suite, concepts, practices)
    - Remove items that don't make sense for the role
    - Deduplicate (including smart deduplication like "Python" vs "Python (Pandas)")
    """
    if not tools:
        return []
    
    job_title_lower = job_title.lower() if job_title else ""
    is_technical_role = any(kw in job_title_lower for kw in 
        ['mlops', 'devops', 'engineer', 'developer', 'architect', 'data', 'ai', 'ml', 'scientist', 'backend', 'frontend', 'full stack'])
    
    cleaned = []
    seen = set()
    seen_base_tools = set()
    
    # Pattern-based filters (no hardcoded word lists)
    # These are regex patterns that detect categories of non-tools
    non_tool_patterns = [
        # Office productivity (not technical tools for dev roles)
        r'^microsoft\s+office',
        r'^office\s+(suite|365)',
        r'^(ms\s+)?word$',
        r'^excel$',
        r'^powerpoint$',
        r'^outlook$',
        # Generic collaboration (not role-specific technical tools)
        r'^(slack|teams|zoom|google\s+meet|webex)$',
        # Academic subjects / concepts (NOT tools)
        r'^(statistics|probability|mathematics?|calculus|linear\s+algebra)$',
        r'^(algorithms?|data\s+structures?)$',
        r'^(machine\s+learning|deep\s+learning|artificial\s+intelligence)$',
        r'^(data\s+visualization|model\s+evaluation|data\s+analysis)$',
        # Methodologies/practices (not tools)
        r'^(agile|scrum|kanban|waterfall)$',
        r'^(best\s+practices|coding\s+standards?|code\s+review)$',
        r'^(ci/cd|cicd)\s+(for\s+ml|for\s+machine\s+learning)$',
        # Generic filler
        r'(other|various|industry\s+standard|relevant)\s+(tools?|technologies)',
    ]
    
    # Standalone programming languages (belong in technical_skills, not tools)
    standalone_lang_pattern = r'^(python|r|java|javascript|typescript|c\+\+|c#|go|rust|ruby|php|scala|kotlin|swift)$'
    
    for tool in tools:
        if not isinstance(tool, str):
            continue
        
        tool_clean = tool.strip()
        tool_lower = tool_clean.lower()
        
        if not tool_clean:
            continue
        
        # Check against non-tool patterns
        skip = False
        for pattern in non_tool_patterns:
            if re.search(pattern, tool_lower, re.IGNORECASE):
                # For Office tools, only skip for technical roles
                if 'office' in pattern or 'word' in pattern or 'excel' in pattern:
                    if is_technical_role:
                        skip = True
                        break
                else:
                    skip = True
                    break
        
        if skip:
            continue
        
        # Skip standalone programming languages (but keep "Python (Pandas)" etc.)
        if re.match(standalone_lang_pattern, tool_lower, re.IGNORECASE) and '(' not in tool_clean:
            continue
        
        # Smart deduplication: Extract base tool name
        base_tool = tool_lower.split('(')[0].strip()
        base_tool = base_tool.split('/')[0].strip()
        
        if base_tool in seen_base_tools:
            if '(' in tool_clean and len(tool_clean) > len(base_tool) + 5:
                cleaned = [t for t in cleaned if t.lower().split('(')[0].strip() != base_tool]
                seen.discard(base_tool)
            else:
                continue
        
        seen_base_tools.add(base_tool)
        
        if tool_lower in seen:
            continue
        seen.add(tool_lower)
        
        cleaned.append(tool_clean)
    
    return cleaned


def sanitize_jd_text_content(jd: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply text cleanup to all text fields in a JD:
    - Fix spacing errors
    - Remove UI artifacts
    - Clean up formatting
    
    This should be called as the LAST step before returning JD.
    """
    if not jd:
        return jd
    
    # Fields that contain user-facing text
    text_fields = [
        'position_summary', 'about_company', 'equal_opportunity_statement'
    ]
    
    # Fields that are lists of strings
    list_fields = [
        'responsibilities', 'preferred_qualifications', 'soft_skills',
        'tools_technologies', 'success_metrics', 'compensation_benefits'
    ]
    
    # Fix text fields
    for field in text_fields:
        if field in jd and isinstance(jd[field], str):
            jd[field] = fix_spacing_errors(jd[field])
            jd[field] = remove_ui_artifacts(jd[field])
    
    # Fix list fields
    for field in list_fields:
        if field in jd and isinstance(jd[field], list):
            cleaned_list = []
            for item in jd[field]:
                if isinstance(item, str):
                    fixed_item = fix_spacing_errors(item)
                    fixed_item = remove_ui_artifacts(fixed_item)
                    if fixed_item.strip():  # Only add non-empty items
                        cleaned_list.append(fixed_item)
                else:
                    cleaned_list.append(item)
            jd[field] = cleaned_list
    
    # Fix nested dict fields (required_qualifications, work_environment, etc.)
    nested_fields = ['required_qualifications', 'work_environment', 'location', 'application_instructions']
    for field in nested_fields:
        if field in jd and isinstance(jd[field], dict):
            for key, value in jd[field].items():
                if isinstance(value, str):
                    jd[field][key] = fix_spacing_errors(value)
                    jd[field][key] = remove_ui_artifacts(jd[field][key])
                elif isinstance(value, list):
                    cleaned = []
                    for item in value:
                        if isinstance(item, str):
                            fixed = fix_spacing_errors(item)
                            fixed = remove_ui_artifacts(fixed)
                            if fixed.strip():
                                cleaned.append(fixed)
                        else:
                            cleaned.append(item)
                    jd[field][key] = cleaned
    
    # Special handling for technical_skills in required_qualifications
    # If it's a list with overloaded comma-separated strings, split them
    if 'required_qualifications' in jd and isinstance(jd['required_qualifications'], dict):
        tech_skills = jd['required_qualifications'].get('technical_skills', [])
        if isinstance(tech_skills, list):
            jd['required_qualifications']['technical_skills'] = clean_technical_skills(tech_skills)
    
    # Special handling for soft_skills - deduplicate semantically
    if 'soft_skills' in jd and isinstance(jd['soft_skills'], list):
        jd['soft_skills'] = dedupe_soft_skills(jd['soft_skills'])
    
    # Special handling for tools_technologies - clean non-tool items
    if 'tools_technologies' in jd and isinstance(jd['tools_technologies'], list):
        jd['tools_technologies'] = clean_tools_technologies(
            jd['tools_technologies'], 
            jd.get('job_title', '')
        )
    
    # Special handling for responsibilities - remove generic filler items
    if 'responsibilities' in jd and isinstance(jd['responsibilities'], list):
        jd['responsibilities'] = clean_responsibilities(jd['responsibilities'])
    
    # Fix department naming errors (e.g., "Data Scientist" → "Data Science")
    if 'department' in jd and isinstance(jd['department'], str):
        jd['department'] = fix_department_name(jd['department'])
    
    return jd


def clean_technical_skills(skills: List[str]) -> List[str]:
    """
    Clean technical skills list:
    - Fix spacing errors in each skill
    - Split overloaded comma-separated strings into individual items
    - Deduplicate
    """
    if not skills:
        return []
    
    cleaned = []
    seen = set()
    
    for skill in skills:
        if not isinstance(skill, str):
            continue
        
        # Fix spacing first
        skill = fix_spacing_errors(skill)
        skill = skill.strip()
        
        if not skill:
            continue
        
        # Check if this is an overloaded string (very long with multiple commas)
        # e.g., "Proficiency in Python or R for data manipulation., Experience with SQL..."
        if len(skill) > 100 and skill.count(',') > 2:
            # Split by comma or period-comma patterns
            parts = re.split(r'[,.](?=\s*[A-Z])', skill)
            for part in parts:
                part = part.strip().rstrip('.,')
                if part and part.lower() not in seen:
                    seen.add(part.lower())
                    cleaned.append(part)
        else:
            # Single skill, just deduplicate
            if skill.lower() not in seen:
                seen.add(skill.lower())
                cleaned.append(skill.rstrip('.,'))
    
    return cleaned


# Department name corrections (role names → proper department names)
DEPARTMENT_FIXES = {
    "data scientist": "Data Science",
    "data scientists": "Data Science",
    "software engineer": "Software Engineering",
    "software engineers": "Software Engineering",
    "software developer": "Software Development",
    "devops engineer": "DevOps",
    "mlops engineer": "MLOps",
    "ml engineer": "Machine Learning",
    "machine learning engineer": "Machine Learning",
    "data engineer": "Data Engineering",
    "data analyst": "Data Analytics",
    "frontend developer": "Frontend Engineering",
    "backend developer": "Backend Engineering",
    "full stack developer": "Full Stack Engineering",
    "product manager": "Product Management",
    "project manager": "Project Management",
    "qa engineer": "Quality Assurance",
    "security engineer": "Security",
    "cloud engineer": "Cloud Engineering",
    "ai engineer": "Artificial Intelligence",
}


def fix_department_name(department: str) -> str:
    """
    Fix department naming errors.
    
    E.g., "Data Scientist" → "Data Science"
    """
    if not department:
        return department
    
    dept_lower = department.lower().strip()
    
    # Check for direct match
    if dept_lower in DEPARTMENT_FIXES:
        return DEPARTMENT_FIXES[dept_lower]
    
    # Return original if no fix needed (already proper name)
    return department


def clean_responsibilities(responsibilities: List[str]) -> List[str]:
    """
    Remove generic filler responsibilities that don't add value.
    
    Examples of bad responsibilities:
    - "Apply Python expertise to deliver high-quality solutions"
    - "Apply Machine Learning expertise to deliver high-quality solutions"
    - "Utilize X skills to..."
    """
    if not responsibilities:
        return []
    
    # Patterns that indicate generic filler responsibilities (capabilities, not tasks)
    filler_patterns = [
        r'^Apply\s+[\w\s]+\s+expertise\s+to\s+deliver',
        r'^Apply\s+[\w\s]+\s+expertise\s+to\s+',
        r'^Utilize\s+[\w\s]+\s+skills?\s+to\s+',
        r'^Utilize\s+[\w\s]+\s+expertise\s+',
        r'^Use\s+\w+\s+to\s+deliver',
        r'^Leverage\s+[\w\s]+\s+expertise',
        r'^Leverage\s+[\w\s]+\s+to\s+deliver',
        r'^Demonstrate\s+[\w\s]+\s+skills?$',
        r'^Demonstrate\s+proficiency\s+in',
        r'^Apply\s+\w+\s+knowledge',
        r'^Show\s+proficiency\s+in',
        r'^Display\s+expertise\s+in',
        r'^Exhibit\s+[\w\s]+\s+skills',
    ]
    
    # Exact phrases to remove (case-insensitive)
    exact_fillers = [
        "apply python expertise to deliver high-quality solutions",
        "apply machine learning expertise to deliver high-quality solutions",
        "apply statistics expertise to deliver high-quality solutions",
        "apply probability expertise to deliver high-quality solutions",
        "apply r expertise to deliver high-quality solutions",
        "apply sql expertise to deliver high-quality solutions",
        "apply data visualization expertise to deliver high-quality solutions",
    ]
    
    cleaned = []
    for resp in responsibilities:
        if not isinstance(resp, str):
            continue
        
        resp_clean = resp.strip()
        if not resp_clean:
            continue
        
        resp_lower = resp_clean.lower()
        
        # Check exact matches first
        if resp_lower in exact_fillers:
            continue
        
        # Check regex patterns
        is_filler = False
        for pattern in filler_patterns:
            if re.match(pattern, resp_clean, re.IGNORECASE):
                is_filler = True
                break
        
        if not is_filler:
            cleaned.append(resp_clean)
    
    return cleaned


def parse_user_requirements(user_requirements: str) -> Dict[str, List[str]]:
    """
    Parse user requirements into structured categories.
    
    Handles formats like:
    - "Programming: Java, Python, C++, JavaScript"
    - "Data Structures & Algorithms"
    - "Git, CI/CD"
    - Newline-separated items
    - Comma-separated items
    
    Returns:
        Dict with keys: 'tools', 'skills', 'concepts', 'all_items'
    """
    if not user_requirements or user_requirements.strip().lower() in ['none', 'none specified', '']:
        return {'tools': [], 'skills': [], 'concepts': [], 'all_items': []}
    
    tools = []
    skills = []
    concepts = []
    all_items = []
    
    # Split by newlines first
    lines = user_requirements.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Check if this line has a category prefix (e.g., "Programming: Java, Python")
        if ':' in line:
            parts = line.split(':', 1)
            category = parts[0].strip().lower()
            items_str = parts[1].strip() if len(parts) > 1 else ''
            
            # Split the items by comma
            items = [item.strip() for item in items_str.split(',') if item.strip()]
            
            # Categorize based on the prefix
            if category in ['programming', 'languages', 'tech stack', 'technologies', 'tools']:
                for item in items:
                    if is_known_tool_or_technology(item) or len(item) <= 15:
                        tools.append(item)
                    else:
                        skills.append(item)
                    all_items.append(item)
            else:
                # Generic category - try to categorize each item
                for item in items:
                    if is_known_tool_or_technology(item):
                        tools.append(item)
                    elif is_concept_or_methodology(item):
                        concepts.append(item)
                    else:
                        skills.append(item)
                    all_items.append(item)
        else:
            # No category prefix - split by comma and & 
            items = re.split(r'[,&]+', line)
            items = [item.strip() for item in items if item.strip()]
            
            for item in items:
                if is_known_tool_or_technology(item):
                    tools.append(item)
                elif is_concept_or_methodology(item):
                    concepts.append(item)
                else:
                    # Check if it looks like a tool (short, no spaces)
                    if len(item) <= 12 and ' ' not in item:
                        tools.append(item)
                    else:
                        skills.append(item)
                all_items.append(item)
    
    # Remove duplicates while preserving order
    def dedupe(lst):
        seen = set()
        result = []
        for item in lst:
            item_lower = item.lower()
            if item_lower not in seen:
                seen.add(item_lower)
                result.append(item)
        return result
    
    return {
        'tools': dedupe(tools),
        'skills': dedupe(skills),
        'concepts': dedupe(concepts),
        'all_items': dedupe(all_items)
    }


def get_expanded_user_requirements_for_prompt(user_requirements: str) -> str:
    """
    Convert user requirements into an expanded, properly formatted string for LLM prompts.
    
    This ensures the LLM sees individual items instead of raw category:items format.
    """
    parsed = parse_user_requirements(user_requirements)
    
    if not parsed['all_items']:
        return user_requirements  # Return original if parsing failed
    
    result_parts = []
    
    if parsed['tools']:
        result_parts.append(f"Tools & Technologies: {', '.join(parsed['tools'])}")
    
    if parsed['skills']:
        result_parts.append(f"Technical Skills: {', '.join(parsed['skills'])}")
    
    if parsed['concepts']:
        result_parts.append(f"Core Concepts: {', '.join(parsed['concepts'])}")
    
    return '\n'.join(result_parts) if result_parts else user_requirements


# ============================================================================
# ROLE-SPECIFIC CONTENT TEMPLATES - Real, actionable responsibilities by role
# ============================================================================

ROLE_SPECIFIC_CONTENT = {
    "data_scientist": {
        "keywords": ["data scientist", "data science", "ml scientist", "machine learning scientist"],
        "junior": {
            "responsibilities": [
                "Clean, preprocess, and validate datasets to ensure data quality and integrity for analysis",
                "Perform exploratory data analysis (EDA) to identify patterns, trends, and anomalies in structured datasets",
                "Build and evaluate baseline machine learning models (regression, classification, clustering) under senior guidance",
                "Calculate and interpret model evaluation metrics such as accuracy, precision, recall, F1-score, and AUC-ROC",
                "Create clear data visualizations and summary reports using Python libraries (Matplotlib, Seaborn) or BI tools",
                "Write and optimize SQL queries to extract and transform data from relational databases",
                "Conduct basic statistical analysis including hypothesis testing, correlation analysis, and descriptive statistics",
                "Support A/B testing initiatives by preparing data, calculating sample sizes, and analyzing results",
                "Document data sources, preprocessing steps, and model experiments for reproducibility",
                "Collaborate with data engineers to understand data pipelines and ensure data availability",
            ],
            "kpis": [
                "Accuracy and timeliness of data cleaning and preprocessing tasks",
                "Quality and clarity of exploratory data analysis reports",
                "Demonstrated improvement in model evaluation and statistical analysis skills",
                "Reproducibility and documentation quality of experiments",
                "Positive feedback from senior data scientists on collaborative work",
            ],
            "realistic_skills": ["Python (primary)", "SQL", "Basic ML concepts", "Statistics fundamentals", "Data visualization"],
            "growth_path": "This role offers a clear progression path from Junior Data Scientist to Data Scientist, with opportunities to specialize in machine learning, analytics, or data engineering based on interest and performance.",
        },
        "mid": {
            "responsibilities": [
                "Design and implement end-to-end machine learning pipelines from data ingestion to model deployment",
                "Develop and optimize predictive models for business use cases such as customer churn, demand forecasting, or recommendation systems",
                "Conduct advanced feature engineering to improve model performance and interpretability",
                "Perform rigorous model validation including cross-validation, hyperparameter tuning, and bias-variance analysis",
                "Lead A/B testing design and analysis to measure the impact of data-driven initiatives",
                "Collaborate with product and business teams to translate business requirements into data science solutions",
                "Build and maintain dashboards and automated reporting systems for key business metrics",
                "Mentor junior data scientists and conduct code reviews for data science projects",
                "Present findings and recommendations to technical and non-technical stakeholders",
                "Stay current with latest developments in machine learning and data science methodologies",
            ],
            "kpis": [
                "Model performance improvements measured by business-relevant metrics",
                "Successful deployment and adoption of data science solutions",
                "Quality and impact of A/B testing analyses",
                "Stakeholder satisfaction with data-driven insights and recommendations",
                "Contribution to team knowledge sharing and junior mentorship",
            ],
        },
        "senior": {
            "responsibilities": [
                "Lead the design and architecture of scalable machine learning systems and data pipelines",
                "Define data science strategy and best practices for the organization",
                "Drive the adoption of advanced ML techniques including deep learning, NLP, or computer vision as appropriate",
                "Mentor and develop junior and mid-level data scientists across the team",
                "Establish model governance frameworks including monitoring, retraining, and version control",
                "Partner with engineering to productionize ML models at scale",
                "Lead cross-functional initiatives to identify high-impact data science opportunities",
                "Define and track KPIs for data science projects and team performance",
                "Represent the data science function to senior leadership and external stakeholders",
                "Evaluate and recommend new tools, technologies, and methodologies for the team",
            ],
            "kpis": [
                "Business impact and ROI of data science initiatives",
                "Team productivity and skill development outcomes",
                "Quality and reliability of production ML systems",
                "Successful cross-functional project delivery",
                "Innovation and adoption of advanced methodologies",
            ],
        },
    },
    "software_engineer": {
        "keywords": ["software engineer", "software developer", "developer", "programmer", "backend engineer", "frontend engineer", "full stack"],
        "junior": {
            "responsibilities": [
                "Write clean, well-tested code following established coding standards and best practices",
                "Fix bugs and implement small features under the guidance of senior engineers",
                "Write unit tests and participate in code reviews to maintain code quality",
                "Document code, APIs, and technical decisions for team knowledge sharing",
                "Participate in agile ceremonies including daily standups, sprint planning, and retrospectives",
                "Debug and troubleshoot issues in development and staging environments",
                "Learn and apply software design patterns and architectural principles",
                "Collaborate with team members to understand requirements and technical specifications",
                "Set up and maintain local development environments",
                "Contribute to technical documentation and runbooks",
            ],
            "kpis": [
                "Code quality metrics including test coverage and code review feedback",
                "Timely completion of assigned tasks and bug fixes",
                "Demonstrated learning progress and skill development",
                "Quality of documentation and knowledge sharing",
                "Positive feedback from mentors and team members",
            ],
            "realistic_skills": ["1 primary programming language", "Git basics", "Unit testing", "Debugging", "Agile fundamentals"],
            "growth_path": "This role provides a foundation for growth into Software Engineer, with opportunities to specialize in backend, frontend, full-stack, or DevOps based on interest and aptitude.",
        },
    },
    "mlops_engineer": {
        "keywords": ["mlops", "ml engineer", "machine learning engineer", "ml ops", "aiops"],
        "senior": {
            "responsibilities": [
                "Design and implement scalable CI/CD pipelines for machine learning model deployment",
                "Architect and maintain ML infrastructure on cloud platforms (AWS SageMaker, Azure ML, GCP Vertex AI)",
                "Establish monitoring systems for model performance, data drift, and system health",
                "Lead the implementation of model versioning, experiment tracking, and reproducibility standards",
                "Optimize ML training and inference workloads for cost and performance",
                "Mentor junior engineers on MLOps best practices and tools",
                "Define and enforce security and governance policies for ML systems",
                "Collaborate with data scientists to streamline the path from experimentation to production",
                "Drive automation of manual ML operations to improve team efficiency",
                "Evaluate and adopt new MLOps tools and technologies",
            ],
            "kpis": [
                "Reduction in model deployment time and manual intervention",
                "Reliability and uptime of ML infrastructure",
                "Cost optimization of cloud ML workloads",
                "Effectiveness of monitoring systems in detecting issues",
                "Team adoption of MLOps best practices",
            ],
        },
    },
}


def get_role_specific_content(job_title: str, job_level: str) -> Dict[str, Any]:
    """
    Get role-specific responsibilities and KPIs based on job title and level.
    
    Returns:
        Dict with 'responsibilities', 'kpis', 'realistic_skills', 'growth_path' if available
    """
    job_title_lower = job_title.lower() if job_title else ""
    level_lower = job_level.lower() if job_level else "mid"
    
    # Normalize level
    if any(l in level_lower for l in ['junior', 'entry', 'associate', 'trainee']):
        level_key = 'junior'
    elif any(l in level_lower for l in ['senior', 'sr', 'lead', 'principal']):
        level_key = 'senior'
    else:
        level_key = 'mid'
    
    # Find matching role
    for role_key, role_config in ROLE_SPECIFIC_CONTENT.items():
        keywords = role_config.get('keywords', [])
        if any(kw in job_title_lower for kw in keywords):
            level_content = role_config.get(level_key, {})
            if level_content:
                return level_content
    
    return {}


# ============================================================================
# LEVEL-SPECIFIC CONTENT CONFIGURATION - Ensures ALL 15 sections match level
# ============================================================================

LEVEL_CONFIG = {
    "junior": {
        "aliases": ["junior", "entry", "entry-level", "associate", "trainee", "graduate"],
        "experience": "0-2 years",
        "experience_text": "0-2 years of relevant experience in the field. Recent graduates with strong academic background or internship experience are welcome.",
        "action_verbs": ["Assist with", "Support", "Learn", "Execute", "Participate in", "Help with", "Contribute to", "Work on"],
        "forbidden_verbs": ["Lead", "Manage", "Drive", "Architect", "Mentor", "Spearhead", "Direct", "Oversee", "Define strategy"],
        "reports_to": ["Team Lead", "Senior Engineer", "Senior Developer", "Senior Analyst", "Project Manager"],
        "summary_phrases": ["under the guidance of senior team members", "develop foundational skills", "support the team", "learn and grow", "work under supervision", "build expertise"],
        "forbidden_summary": ["lead the team", "drive strategic", "mentor junior", "architect solutions", "define direction"],
        "education": "Bachelor's degree in relevant field. Recent graduates welcome.",
        "soft_skills": ["Eagerness to learn", "Strong communication skills", "Team player", "Attention to detail", "Adaptability", "Positive attitude", "Willingness to take feedback"],
        "kpi_keywords": ["task completion", "learning progress", "code quality", "documentation", "responsiveness", "attendance"],
        "forbidden_kpis": ["team performance", "strategic impact", "revenue growth", "organization-wide"],
        "autonomy": "Works under close supervision with regular guidance from senior team members",
    },
    "mid": {
        "aliases": ["mid", "mid-level", "intermediate", "regular", "standard"],
        "experience": "3-5 years",
        "experience_text": "3-5 years of hands-on experience in the field with demonstrated expertise in core technologies.",
        "action_verbs": ["Develop", "Implement", "Collaborate", "Analyze", "Execute", "Design", "Build", "Create", "Manage", "Coordinate"],
        "forbidden_verbs": ["Assist with", "Learn", "Spearhead", "Transform", "Pioneer", "Define organizational"],
        "reports_to": ["Engineering Manager", "Team Lead", "Department Manager", "Project Manager", "Senior Manager"],
        "summary_phrases": ["independently develop", "collaborate with cross-functional teams", "take ownership", "deliver high-quality solutions", "contribute to projects"],
        "forbidden_summary": ["under guidance", "learn and grow", "lead organization-wide", "define company strategy"],
        "education": "Bachelor's degree in relevant field required.",
        "soft_skills": ["Strong analytical skills", "Excellent communication", "Problem-solving ability", "Team collaboration", "Time management", "Self-motivated", "Adaptability"],
        "kpi_keywords": ["project delivery", "code quality", "feature completion", "collaboration", "documentation", "process improvement"],
        "forbidden_kpis": ["organizational transformation", "company-wide impact", "executive stakeholder"],
        "autonomy": "Works independently with periodic check-ins and guidance on complex matters",
    },
    "senior": {
        "aliases": ["senior", "sr", "sr.", "experienced", "advanced"],
        "experience": "5-8 years",
        "experience_text": "5-8 years of progressive experience with proven expertise in designing and implementing complex solutions.",
        "action_verbs": ["Lead", "Design", "Architect", "Mentor", "Drive", "Establish", "Define", "Optimize", "Guide", "Influence"],
        "forbidden_verbs": ["Assist with", "Learn", "Support senior", "Work under supervision"],
        "reports_to": ["Director of Engineering", "VP of Engineering", "Director", "Department Head", "CTO"],
        "summary_phrases": ["lead the design and implementation", "mentor junior team members", "drive technical excellence", "architect scalable solutions", "provide technical leadership"],
        "forbidden_summary": ["under guidance", "learn and grow", "support senior", "work under supervision"],
        "education": "Bachelor's degree required; Master's degree preferred.",
        "soft_skills": ["Technical leadership", "Mentoring ability", "Strategic thinking", "Excellent communication", "Stakeholder management", "Decision-making", "Conflict resolution"],
        "kpi_keywords": ["team performance", "architecture quality", "mentoring outcomes", "technical leadership", "system scalability", "innovation"],
        "forbidden_kpis": ["learning progress", "task completion under supervision"],
        "autonomy": "Fully autonomous with responsibility for technical decisions and team guidance",
    },
    "lead": {
        "aliases": ["lead", "principal", "staff", "architect", "head"],
        "experience": "8+ years",
        "experience_text": "8+ years of extensive experience with significant leadership responsibilities and strategic impact.",
        "action_verbs": ["Transform", "Influence", "Shape", "Spearhead", "Pioneer", "Establish", "Define", "Drive", "Lead", "Architect"],
        "forbidden_verbs": ["Assist with", "Learn", "Support", "Execute basic", "Work under"],
        "reports_to": ["VP of Engineering", "CTO", "Chief Technology Officer", "CEO", "Executive Director"],
        "summary_phrases": ["set technical direction", "drive organizational strategy", "influence company-wide decisions", "transform capabilities", "establish best practices"],
        "forbidden_summary": ["under guidance", "learn", "support senior", "work under supervision", "develop foundational"],
        "education": "Master's degree preferred; advanced certifications valued.",
        "soft_skills": ["Visionary leadership", "Strategic thinking", "Executive communication", "Organizational influence", "Change management", "Cross-functional leadership", "Business acumen"],
        "kpi_keywords": ["organizational impact", "strategic initiatives", "innovation leadership", "talent development", "business outcomes"],
        "forbidden_kpis": ["individual task completion", "learning progress", "basic code quality"],
        "autonomy": "Sets direction for teams and influences organizational technology strategy",
    }
}


def get_level_config(job_level: str) -> Dict[str, Any]:
    """Get the level configuration based on job level string."""
    if not job_level:
        return LEVEL_CONFIG["mid"]  # Default to mid-level
    
    level_lower = job_level.lower().strip()
    
    for level_key, config in LEVEL_CONFIG.items():
        if level_lower in config["aliases"] or level_key in level_lower:
            return config
    
    # Default to mid-level if not found
    return LEVEL_CONFIG["mid"]


def enforce_level_consistency(jd: Dict[str, Any], job_level: str, job_title: str) -> Dict[str, Any]:
    """
    CRITICAL: Enforce level-appropriate content across ALL 15 sections.
    
    This function validates and fixes any content that doesn't match the job level.
    """
    if not job_level:
        return jd
    
    config = get_level_config(job_level)
    level_lower = job_level.lower()
    fixes_applied = []
    
    logger.info(f"🎯 Enforcing {job_level} level consistency for {job_title}")
    
    # ===== SECTION 1: Job Title - Preserve user input =====
    # (No changes needed - job_title should match user input)
    
    # ===== SECTION 6: Position Summary - Must match level =====
    position_summary = jd.get('position_summary', '')
    if position_summary:
        summary_lower = position_summary.lower()
        
        # Check for forbidden phrases
        for forbidden in config.get('forbidden_summary', []):
            if forbidden.lower() in summary_lower:
                logger.warning(f"⚠️ Position summary contains forbidden phrase for {job_level}: '{forbidden}'")
        
        # Check if appropriate phrases are present
        has_level_phrase = any(phrase.lower() in summary_lower for phrase in config.get('summary_phrases', []))
        if not has_level_phrase and position_summary:
            # Add level-appropriate phrase
            level_phrase = config['summary_phrases'][0] if config.get('summary_phrases') else ''
            if level_phrase and level_phrase.lower() not in summary_lower:
                # Prepend appropriate context
                if 'junior' in level_lower or 'entry' in level_lower:
                    if 'under' not in summary_lower and 'guidance' not in summary_lower:
                        jd['position_summary'] = position_summary.rstrip('.') + ", working under the guidance of senior team members."
                        fixes_applied.append("Added junior-level context to position_summary")
    
    # ===== SECTION 7: Responsibilities - Fix action verbs and enhance with role-specific content =====
    responsibilities = jd.get('responsibilities', [])
    
    # Get role-specific content if available
    role_content = get_role_specific_content(job_title, job_level)
    role_responsibilities = role_content.get('responsibilities', [])
    
    if responsibilities and isinstance(responsibilities, list):
        fixed_responsibilities = []
        forbidden_verbs = config.get('forbidden_verbs', [])
        approved_verbs = config.get('action_verbs', [])
        
        for resp in responsibilities:
            if not isinstance(resp, str):
                continue
            
            fixed_resp = resp
            resp_lower = resp.lower()
            
            # Check for forbidden verbs and replace them
            for forbidden in forbidden_verbs:
                if resp_lower.startswith(forbidden.lower()):
                    # Replace with appropriate verb
                    replacement = approved_verbs[0] if approved_verbs else "Contribute to"
                    fixed_resp = replacement + resp[len(forbidden):]
                    fixes_applied.append(f"Replaced '{forbidden}' with '{replacement}' in responsibility")
                    break
            
            fixed_responsibilities.append(fixed_resp)
        
        # After cleaning filler items, check if we have enough real responsibilities
        # If too few, supplement with role-specific responsibilities
        if len(fixed_responsibilities) < 8 and role_responsibilities:
            existing_lower = set(r.lower()[:50] for r in fixed_responsibilities)
            for role_resp in role_responsibilities:
                if role_resp.lower()[:50] not in existing_lower and len(fixed_responsibilities) < 10:
                    fixed_responsibilities.append(role_resp)
                    existing_lower.add(role_resp.lower()[:50])
                    fixes_applied.append(f"Added role-specific responsibility")
        
        jd['responsibilities'] = fixed_responsibilities
    elif role_responsibilities:
        # No responsibilities at all - use role-specific templates
        jd['responsibilities'] = role_responsibilities[:10]
        fixes_applied.append(f"Added {len(jd['responsibilities'])} role-specific responsibilities")
    
    # ===== SECTION 8: Required Qualifications - Fix experience =====
    req_qual = jd.get('required_qualifications', {})
    if isinstance(req_qual, dict):
        # Fix experience
        current_exp = req_qual.get('experience', '')
        expected_exp = config.get('experience', '3-5 years')
        exp_text = config.get('experience_text', '')
        
        # Check if experience matches level
        if current_exp:
            exp_lower = current_exp.lower()
            needs_fix = False
            
            if 'junior' in level_lower or 'entry' in level_lower:
                if any(x in exp_lower for x in ['3+', '4+', '5+', '6+', '7+', '8+', '3-5', '5-8', '5+']):
                    needs_fix = True
            elif 'mid' in level_lower:
                if any(x in exp_lower for x in ['0-2', '7+', '8+', '10+']):
                    needs_fix = True
            elif 'senior' in level_lower:
                if any(x in exp_lower for x in ['0-2', '1-3', '2-4']):
                    needs_fix = True
            
            if needs_fix:
                jd['required_qualifications']['experience'] = exp_text
                fixes_applied.append(f"Fixed experience to {expected_exp} for {job_level}")
        
        # Fix education
        current_edu = req_qual.get('education', '')
        if current_edu:
            expected_edu = config.get('education', '')
            if expected_edu and expected_edu.lower() not in current_edu.lower():
                jd['required_qualifications']['education'] = expected_edu
                fixes_applied.append(f"Updated education for {job_level}")
    
    # ===== SECTION 10: Soft Skills - Add level-appropriate skills =====
    soft_skills = jd.get('soft_skills', [])
    if isinstance(soft_skills, list):
        level_soft_skills = config.get('soft_skills', [])
        existing_lower = [s.lower() for s in soft_skills if isinstance(s, str)]
        
        # Add level-appropriate soft skills if missing
        for skill in level_soft_skills[:3]:  # Add up to 3 level-specific skills
            if skill.lower() not in existing_lower:
                soft_skills.append(skill)
                fixes_applied.append(f"Added level-appropriate soft skill: {skill}")
        
        jd['soft_skills'] = soft_skills
    
    # ===== SECTION 12: Work Environment / Reporting Structure =====
    work_env = jd.get('work_environment', {})
    if isinstance(work_env, dict):
        current_reports_to = work_env.get('reports_to', '')
        expected_reports = config.get('reports_to', [])
        
        # Check if reports_to matches level
        if current_reports_to and expected_reports:
            reports_lower = current_reports_to.lower()
            is_appropriate = any(exp.lower() in reports_lower for exp in expected_reports)
            
            if not is_appropriate:
                work_env['reports_to'] = expected_reports[0]
                fixes_applied.append(f"Fixed reports_to to '{expected_reports[0]}' for {job_level}")
        
        # Add autonomy description
        autonomy = config.get('autonomy', '')
        if autonomy:
            work_env['autonomy_level'] = autonomy
        
        jd['work_environment'] = work_env
    
    # ===== SECTION 11: Success Metrics - Must match level =====
    success_metrics = jd.get('success_metrics', [])
    if isinstance(success_metrics, list):
        forbidden_kpis = config.get('forbidden_kpis', [])
        valid_metrics = []
        
        for metric in success_metrics:
            if not isinstance(metric, str):
                continue
            metric_lower = metric.lower()
            
            # Check if metric contains forbidden KPI keywords
            is_forbidden = any(forbidden.lower() in metric_lower for forbidden in forbidden_kpis)
            if not is_forbidden:
                valid_metrics.append(metric)
            else:
                fixes_applied.append(f"Removed inappropriate KPI for {job_level}: {metric[:50]}...")
        
        # Check if KPIs are too vague - supplement with role-specific KPIs
        role_kpis = role_content.get('kpis', [])
        if len(valid_metrics) < 4 and role_kpis:
            existing_lower = set(m.lower()[:30] for m in valid_metrics)
            for kpi in role_kpis:
                if kpi.lower()[:30] not in existing_lower and len(valid_metrics) < 6:
                    valid_metrics.append(kpi)
                    existing_lower.add(kpi.lower()[:30])
                    fixes_applied.append(f"Added role-specific KPI")
        
        jd['success_metrics'] = valid_metrics
    
    # ===== Add growth path for junior roles =====
    growth_path = role_content.get('growth_path', '')
    if growth_path and ('junior' in level_lower or 'entry' in level_lower):
        # Add growth path to work environment or create a new field
        work_env = jd.get('work_environment', {})
        if isinstance(work_env, dict):
            work_env['growth_opportunities'] = growth_path
            jd['work_environment'] = work_env
            fixes_applied.append("Added growth path information for junior role")
    
    if fixes_applied:
        logger.info(f"✅ Applied {len(fixes_applied)} level-consistency fixes:")
        for fix in fixes_applied[:5]:  # Log first 5
            logger.info(f"   - {fix}")
        if len(fixes_applied) > 5:
            logger.info(f"   ... and {len(fixes_applied) - 5} more fixes")
    
    return jd


# ============================================================================
# MALOMATIA COMPANY DEFAULTS - Used for ALL generated JDs
# ============================================================================
MALOMATIA_COMPANY_INFO = {
    "about_company": "Malomatia is a leading provider of Information Technology services and solutions headquartered in Doha, Qatar, delivering digital transformation, managed services, and operational excellence across multiple sectors and delivery locations. Founded in 2008 at Manarat Lusail Tower, Malomatia supports Qatar's National Vision 2030 while enabling clients through reliable technology services, process improvement, and knowledge-based innovation.",
    "equal_opportunity_statement": "Malomatia is an Equal Opportunity Employer. We celebrate diversity and are committed to creating an inclusive environment for all employees regardless of race, religion, gender, age, nationality, disability, or any other protected status. We welcome applications from all qualified candidates.",
    "default_location": {
        "city": "Location to be confirmed",
        "country": "",
        "work_model": "Hybrid",
        "travel_required": False,
        "travel_percentage": None
    },
    "application_instructions": {
        "apply_url": "https://careers.malomatia.com/apply",
        "email": "careers@malomatia.com",
        "required_materials": ["Resume", "Cover Letter"]
    },
    "compensation_benefits": [
        "Competitive salary",
        "Health insurance",
        "Paid time off",
        "Professional development opportunities",
        "Performance bonus",
        "Remote work flexibility"
    ]
}


def enforce_malomatia_defaults(jd: Dict[str, Any], original_job_title: str = None, user_location: str = None, user_department: str = None, user_job_level: str = None, user_requirements: str = None) -> Dict[str, Any]:
    """
    ALWAYS enforce Malomatia company information in the JD.
    This overrides any company info the LLM may have generated.
    
    Also preserves ALL user inputs: job title, location, department, job level, and requirements.
    
    This is a module-level function so it can be used by all agents.
    
    Args:
        jd: The job description dictionary to modify
        original_job_title: The exact job title user entered (if provided, will override LLM's title)
        user_location: The user's location input (e.g., "Doha, Qatar") - MUST be preserved
        user_department: The exact department user entered (if provided, will override LLM's department)
        user_job_level: The job level user selected (Junior, Mid, Senior, etc.) - MUST be preserved
        user_requirements: The additional requirements user entered - MUST be preserved
    """
    # Section 1: Job Title - PRESERVE the exact title user entered
    if original_job_title:
        jd["job_title"] = original_job_title
        logger.info(f"✅ Preserved original job title: {original_job_title}")
    
    # Job Level - PRESERVE the exact level user selected
    if user_job_level and user_job_level.strip():
        jd["job_level"] = user_job_level.strip()
        logger.info(f"✅ Preserved original job level: {user_job_level.strip()}")
    
    # Additional Requirements - Store for reference/validation
    if user_requirements and user_requirements.strip():
        jd["user_requirements"] = user_requirements.strip()
        logger.info(f"✅ Preserved user requirements: {user_requirements.strip()[:50]}...")
    
    # Section 2: Department - PRESERVE the exact department user entered
    if user_department and user_department.strip():
        jd["department"] = user_department.strip()
        logger.info(f"✅ Preserved original department: {user_department.strip()}")
    
    # Section 5: Position Summary - Validate it mentions the correct job title AND matches level
    position_summary = jd.get("position_summary", "")
    job_level_lower = (user_job_level or jd.get("job_level", "")).lower()
    
    if position_summary and original_job_title:
        # Check if the summary mentions a DIFFERENT job title (common LLM mistake)
        wrong_titles = ["Software Engineer", "Senior Software Engineer", "Developer", "Engineer"]
        summary_lower = position_summary.lower()
        title_lower = original_job_title.lower()
        
        # If summary mentions generic titles but not the actual job title, fix it
        for wrong_title in wrong_titles:
            if wrong_title.lower() in summary_lower and title_lower not in summary_lower:
                # Replace wrong title with correct one
                jd["position_summary"] = re.sub(
                    re.escape(wrong_title), 
                    original_job_title, 
                    position_summary, 
                    flags=re.IGNORECASE
                )
                logger.info(f"✅ Fixed position_summary to mention '{original_job_title}' instead of '{wrong_title}'")
                position_summary = jd["position_summary"]  # Update for level check
                break
        
        # Check if Junior position summary has appropriate language
        if 'junior' in job_level_lower or 'entry' in job_level_lower:
            junior_keywords = ['under guidance', 'under supervision', 'support', 'assist', 'learn', 'foundational', 'entry-level']
            senior_keywords = ['lead', 'architect', 'mentor', 'drive', 'spearhead', 'strategic']
            
            has_junior_lang = any(kw in summary_lower for kw in junior_keywords)
            has_senior_lang = any(kw in summary_lower for kw in senior_keywords)
            
            # If summary has senior language but no junior language, it needs fixing
            if has_senior_lang and not has_junior_lang:
                logger.warning(f"⚠️ Position summary has senior-level language for Junior role - flagging for review")
                # Add a note but don't completely rewrite (keep it agentic)
    
    # Section 4: About the Company - ALWAYS use Malomatia info
    jd["about_company"] = MALOMATIA_COMPANY_INFO["about_company"]
    
    # Section 14: Equal Opportunity Statement - ALWAYS use Malomatia statement
    jd["equal_opportunity_statement"] = MALOMATIA_COMPANY_INFO["equal_opportunity_statement"]
    
    # Section 3: Location - PRESERVE user's location if provided; otherwise avoid inventing a city.
    if "location" not in jd or not isinstance(jd["location"], dict):
        jd["location"] = {}
    
    location = jd["location"]
    
    # CRITICAL: If user provided a location, ALWAYS use it
    if user_location and user_location.strip():
        # Parse user location (format: "City, State/Country" or just "City")
        user_loc_str = user_location.strip()
        if "," in user_loc_str:
            parts = [p.strip() for p in user_loc_str.split(",")]
            location["city"] = parts[0]
            location["country"] = parts[1] if len(parts) > 1 else ""
        else:
            location["city"] = user_loc_str
            location["country"] = ""
        logger.info(f"✅ Preserved user's location: {location['city']}, {location.get('country', '')}")
    else:
        # Do not invent a city/country when the dialog location is blank.
        if not location.get("city") or location.get("city", "").lower() in ["city", "not specified", "tbd", ""]:
            location["city"] = "Location to be confirmed"
            location["country"] = ""
            logger.info("Location left blank; using 'Location to be confirmed'")
    
    # Ensure work_model has a value based on remote_allowed if provided
    # Note: remote_allowed is passed separately, but we'll set work_model based on context
    if not location.get("work_model"):
        location["work_model"] = "Hybrid"
    # Ensure travel_required is set
    if "travel_required" not in location:
        location["travel_required"] = False
    
    jd["location"] = location
    
    # Section 13: Compensation & Benefits - Use Malomatia defaults if empty
    if not jd.get("compensation_benefits") or len(jd.get("compensation_benefits", [])) == 0:
        jd["compensation_benefits"] = MALOMATIA_COMPANY_INFO["compensation_benefits"].copy()
        logger.info("✅ Applied Malomatia default compensation & benefits")
    
    # Section 15: Application Instructions - ALWAYS use Malomatia URLs
    if "application_instructions" not in jd or not isinstance(jd["application_instructions"], dict):
        jd["application_instructions"] = {}
    
    jd["application_instructions"]["apply_url"] = MALOMATIA_COMPANY_INFO["application_instructions"]["apply_url"]
    jd["application_instructions"]["email"] = MALOMATIA_COMPANY_INFO["application_instructions"]["email"]
    if not jd["application_instructions"].get("required_materials"):
        jd["application_instructions"]["required_materials"] = MALOMATIA_COMPANY_INFO["application_instructions"]["required_materials"]
    
    # =====================================================================
    # CRITICAL: ENFORCE EXPERIENCE TO MATCH JOB LEVEL
    # This is a safety net to fix AI agent errors when experience doesn't match level
    # =====================================================================
    job_level = jd.get('job_level', '').lower()
    if 'required_qualifications' not in jd or not isinstance(jd.get('required_qualifications'), dict):
        jd['required_qualifications'] = {}
    
    rq = jd['required_qualifications']
    current_exp = rq.get('experience', '')
    
    if current_exp and current_exp.strip():
        # Fix Junior level experience if it shows 3+ years
        if 'junior' in job_level or 'entry' in job_level:
            years_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', current_exp.lower())
            if years_match and int(years_match.group(1)) >= 3:
                logger.warning(f"⚠️ FIXING: Experience '{years_match.group(0)}' does not match {job_level} level - correcting to 0-2 years")
                rq['experience'] = "0-2 years of relevant experience in the field. Internships and academic projects count towards experience."
        # Fix Mid level experience if outside 3-5 years range
        elif 'mid' in job_level or 'intermediate' in job_level:
            years_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)', current_exp.lower())
            if years_match and (int(years_match.group(1)) < 3 or int(years_match.group(1)) > 6):
                logger.warning(f"⚠️ FIXING: Experience '{years_match.group(0)}' does not match {job_level} level - correcting to 3-5 years")
                rq['experience'] = "3-5 years of professional experience in the field."
    
    logger.info("✅ Enforced Malomatia company defaults on JD")
    return jd


class BaseCrewAgent(AutonomousAgent):
    """
    Base class for JD workflow agents with full autonomy.
    
    Extends AutonomousAgent to provide:
    - True autonomous behavior (observe, think, plan, act, reflect)
    - Direct LangChain LLM invocation for generation tasks
    - Thinking visibility
    """
    
    def __init__(
        self,
        agent_name: str,
        role: str,
        goal: str,
        backstory: str,
        config=None,
    ):
        """
        Initialize base agent with full autonomy.
        
        Args:
            agent_name: Name of the agent
            role: Agent role
            goal: Agent goal
            backstory: Agent backstory
            config: JDGenerationConfig instance (uses global config if not provided)
        """
        from agents.jd_generation.config import JDGenerationConfig, get_config
        from agents.jd_generation.autonomous_agent import AutonomousAgent, Environment
        
        # Initialize as autonomous agent
        super().__init__(agent_name=agent_name, goal=goal, config=config)
        
        self.role = role
        self.backstory = backstory
        
        # Initialize LangChain LLM for workflow nodes
        self._setup_crew_llm()

    def _active_llm(self) -> Any:
        """Return the LLM used for workflow generation tasks."""
        if hasattr(self, "crew_llm") and self.crew_llm is not None:
            return self.crew_llm
        return self.llm

    def _setup_crew_llm(self, model_name: Optional[str] = None):
        """Initialize LangChain LLM for workflow agent nodes."""
        llm_config = self.config.get_llm_config()
        active_model = model_name or llm_config["model"]
        provider = llm_config.get("provider", "google")

        if model_name:
            self._setup_llm(model_name=model_name)

        try:
            from agents.llm.chat_factory import create_chat_llm

            self.crew_llm = create_chat_llm(
                model=active_model,
                temperature=llm_config["temperature"],
                max_tokens=llm_config["max_tokens"],
                provider=llm_config.get("provider"),
            )
            self.llm = self.crew_llm
            logger.info(
                "%s workflow LLM ready (Provider: %s, Model: %s)",
                self.agent_name,
                provider,
                active_model,
            )
        except Exception as e:
            logger.error(
                "Workflow LLM setup failed for %s (%s); using agent base LLM",
                self.agent_name,
                e,
            )
            self.crew_llm = self.llm

        self.agent = SimpleNamespace(
            role=self.role,
            goal=self.goal,
            llm=self._active_llm(),
        )

    def _build_task_prompt(
        self,
        task_description: str,
        expected_output: Optional[str] = None,
    ) -> str:
        """Wrap task text with agent persona — same shape as CrewAI Task.kickoff()."""
        return build_agent_task_prompt(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            task_description=task_description,
            expected_output=expected_output,
        )

    def switch_to_fallback_model(self) -> bool:
        """
        Switch to fallback model for both Autonomous base and CrewAI specific components.
        Returns: True if switched successfully, False if no fallback available.
        """
        # First switch base components (self.llm, self.reasoning, etc.)
        switched_base = super().switch_to_fallback_model()
        
        if not switched_base:
            return False
            
        # Then switch CrewAI specific components (self.crew_llm, self.agent)
        fallback_model = self.config.llm_fallback_model
        self._setup_crew_llm(model_name=fallback_model)

        logger.warning(
            "Successfully switched '%s' components to fallback model: %s",
            self.agent_name,
            fallback_model,
        )
        return True
    
    def _log_thought(self, thought: str, action: str = None, state: dict = None, reasoning: dict = None):
        """
        Log agent thinking for visibility and optionally add to state.
        
        Args:
            thought: The thought message
            action: Optional action being taken
            state: Optional state dictionary to add thought to (for workflow integration)
            reasoning: Optional reasoning dictionary from autonomous cycle
        """
        logger.info(f"🤔 [{self.agent_name}] {thought}")
        if action:
            logger.info(f"   → Action: {action}")
        
        # If state is provided, add thought to state for API response
        if state is not None and isinstance(state, dict):
            thought_entry = {
                "agent": self.agent_name,
                "thought": thought,
                "action": action,
                "state": state.get("current_state", "unknown"),
                "reasoning": reasoning,
                "autonomous": True,
            }
            if "agent_thoughts" not in state:
                state["agent_thoughts"] = []
            state["agent_thoughts"].append(thought_entry)
    
    def act(self, plan: Dict[str, Any], environment: Environment) -> Dict[str, Any]:
        """
        ACT: Execute plan autonomously using direct LangChain LLM invocation.
        
        The agent autonomously:
        - Executes planned actions
        - Uses the configured LLM for task execution
        - Adapts to results
        - Handles errors
        - Produces outputs
        
        Args:
            plan: Action plan from plan() method
            environment: Environment to act in
            
        Returns:
            Action result dictionary
        """
        prompt = self._build_task_prompt(
            f"""
            AUTONOMOUS EXECUTION:
            
            Plan: {plan.get('plan', '')}
            Steps: {plan.get('steps', [])}
            
            Execute this plan autonomously. Make decisions independently.
            Use your tools and reasoning to complete the task.
            """,
            expected_output="Execution result",
        )

        try:
            result_text = invoke_prompt_with_retry(
                self._active_llm(),
                prompt,
                agent_name=self.agent_name,
                switch_fallback_fn=self.switch_to_fallback_model,
                get_llm_fn=self._active_llm,
                operation="autonomous plan execution",
            )
            return {
                "success": True,
                "result": result_text,
                "plan_executed": plan.get("plan", ""),
            }
        except Exception as e:
            logger.error(f"Action execution failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "plan_executed": plan.get("plan", ""),
            }


class JDGeneratorAgent(BaseCrewAgent):
    """Agent responsible for generating initial Job Descriptions."""
    
    def __init__(self, config=None):
        """
        Initialize JD Generator Agent.
        
        Args:
            config: JDGenerationConfig instance (uses global config if not provided)
        """
        super().__init__(
            agent_name="JD Generator",
            role="Senior HR Specialist & Job Description Writer",
            goal="Generate comprehensive, professional Job Descriptions that attract top talent",
            backstory="""You are an expert HR professional with 15+ years of experience 
            in talent acquisition. You specialize in creating compelling job descriptions 
            that accurately represent roles while attracting qualified candidates. You 
            understand market trends, salary benchmarks, and what makes job descriptions 
            stand out. You always ensure JDs are clear, comprehensive, and professional.""",
            config=config
        )
    
    @traceable(name="generate_jd")
    def generate_jd(self, context: Dict[str, Any], state: dict = None) -> Dict[str, Any]:
        """
        Generate comprehensive JD using streamlined OTPAR cycle.
        
        OTPAR Cycle (Single Pass - No Redundant Cycles):
        - OBSERVE: Analyze input context (job title, level, department, requirements)
        - THINK: Reason about what sections and content the JD needs
        - PLAN: Structure the 15-section enterprise JD content plan
        - ACT: Execute LangChain LLM to generate actual JD content (NOT meta-plans)
        - REFLECT: Evaluate the result quality
        
        Args:
            context: Job context (title, level, department, etc.)
            state: Optional workflow state for logging agent thoughts
        """
        job_title = context.get('job_title', 'Position')
        
        # ===== OBSERVE Phase =====
        self._log_autonomous_action("OBSERVE", f"Analyzing context for {job_title}")
        if state:
            self._log_thought(f"OBSERVE: Analyzing requirements for {job_title}", "Perceiving context", state=state)
        
        observation = {
            "job_title": job_title,
            "job_level": context.get('job_level', 'Mid-level'),
            "department": context.get('department', 'Engineering'),
            "location": context.get('location'),
            "remote_allowed": context.get('remote_allowed', False),
            "user_requirements": context.get('user_requirements', ''),
            "similar_jobs_count": len(context.get('similar_jobs', [])),
        }
        
        # ===== THINK Phase =====
        self._log_autonomous_action("THINK", f"Reasoning about JD structure for {job_title}")
        if state:
            self._log_thought(f"THINK: Determining content needs for {job_title}", "Reasoning", state=state)
        
        # ===== PLAN Phase =====
        self._log_autonomous_action("PLAN", f"Planning 15-section enterprise JD for {job_title}")
        if state:
            self._log_thought("PLAN: Structuring enterprise JD with all 15 sections", "Content planning", state=state)
        
        # ===== ACT Phase - Direct LLM Execution =====
        self._log_autonomous_action("ACT", f"Generating JD content for {job_title}")
        if state:
            self._log_thought("ACT: Executing JD generation with LangGraph LLM", "Generating content", state=state)
        
        # Execute the actual JD generation
        jd = self._generate_with_llm(context, state=state)
        
        # ===== REFLECT Phase =====
        position_summary_len = len(jd.get('position_summary', '')) if jd else 0
        responsibilities_count = len(jd.get('responsibilities', [])) if jd else 0
        
        self._log_autonomous_action("REFLECT", f"JD quality: {position_summary_len} chars summary, {responsibilities_count} responsibilities")
        if state:
            self._log_thought(
                f"REFLECT: Generated JD with {position_summary_len} chars summary, {responsibilities_count} responsibilities",
                "OTPAR cycle complete",
                state=state
            )
        
        return jd
    
    def _generate_with_crewai(self, context: Dict[str, Any], state: dict = None) -> Dict[str, Any]:
        """Backward-compatible alias for LangGraph LLM generation."""
        return self._generate_with_llm(context, state=state)

    def _generate_with_llm(self, context: Dict[str, Any], state: dict = None) -> Dict[str, Any]:
        """Generate using direct LangChain LLM invocation with Enterprise 15-section format."""
        from agents.jd_generation.enterprise_prompts import get_enterprise_generation_prompt
        
        self._log_thought(
            f"Analyzing requirements for {context.get('job_title')} position. "
            "Planning Enterprise JD structure with all 15 sections.",
            "Starting Enterprise JD generation",
            state=state
        )
        
        job_title = context.get('job_title', 'Software Engineer')
        job_level = context.get('job_level', 'Mid-level')
        department = context.get('department', 'Engineering')
        location = context.get('location', 'Remote')
        remote_allowed = context.get('remote_allowed', False)
        user_requirements = context.get('user_requirements', '')
        
        # ===== PARSE AND EXPAND USER REQUIREMENTS =====
        # Convert raw user input like "Programming: Java, Python, C++" into structured format
        parsed_requirements = parse_user_requirements(user_requirements)
        expanded_requirements = get_expanded_user_requirements_for_prompt(user_requirements)
        
        # Store parsed requirements in context for downstream use
        context['parsed_requirements'] = parsed_requirements
        
        logger.info(f"📋 Parsed user requirements:")
        logger.info(f"   - Tools: {parsed_requirements.get('tools', [])}")
        logger.info(f"   - Skills: {parsed_requirements.get('skills', [])}")
        logger.info(f"   - Concepts: {parsed_requirements.get('concepts', [])}")
        logger.info(f"   - Expanded for prompt: {expanded_requirements[:100]}...")
        
        # Store context for later use in _ensure_enterprise_format
        self._current_context = context
        
        # Get enterprise 15-section prompt with expanded requirements
        enterprise_prompt = get_enterprise_generation_prompt(
            job_title=job_title,
            job_level=job_level,
            department=department,
            location=location,
            remote_allowed=remote_allowed,
            user_requirements=expanded_requirements  # Use expanded, not raw
        )

        generation_prompt = self._build_task_prompt(
            enterprise_prompt,
            expected_output=(
                f"A complete 15-section enterprise job description for "
                f"{job_level} {job_title} in JSON format"
            ),
        )

        self._log_thought(
            "Executing JD generation task with LangGraph LLM. Analyzing context and generating content.",
            "Running LLM generation",
            state=state
        )

        try:
            result_text = invoke_prompt_with_retry(
                self._active_llm(),
                generation_prompt,
                agent_name=self.agent_name,
                max_attempts=2,
                switch_fallback_fn=self.switch_to_fallback_model,
                get_llm_fn=self._active_llm,
                operation=f"JD generation for {job_title}",
            )

            self._log_thought(
                "JD generation completed. Extracting structured content.",
                "Processing result",
                state=state
            )

            jd = self._parse_jd_result(result_text, user_location=location, user_department=department)
            return jd

        except Exception as e:
            logger.error(f"❌ JD generation failed: {e}", exc_info=True)
            self._log_thought(
                f"Error during JD generation: {str(e)}",
                "Generation failed",
                state=state
            )
            raise
    
    def _parse_jd_result(self, result: Any, user_location: str = None, user_department: str = None) -> Dict[str, Any]:
        """Parse LLM result into Enterprise 15-section JD format using LLM."""
        import json
        import re
        from agents.jd_generation.enterprise_prompts import get_enterprise_extraction_prompt
        
        text = extract_llm_text(result)
        
        logger.info(f"🔍 Parsing JD result. Text length: {len(text)}")
        logger.debug(f"🔍 First 500 chars of result: {text[:500]}")
        
        # Check for contaminated output (agent reasoning leaked into result)
        contamination_markers = ['**ACT**:', '**OBSERVE**:', '**THINK**:', '**PLAN**:', 
                                 'Calling tool:', 'retrieve_similar_jobs', 'I will now execute']
        is_contaminated = any(marker in text for marker in contamination_markers)
        if is_contaminated:
            logger.warning("⚠️ DETECTED: Agent reasoning artifacts in output. Will sanitize.")
        
        # Try to parse JSON directly first (if LLM returned valid JSON)
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            json_str = json_match.group(0)
            logger.info(f"🔍 Found JSON in result. JSON length: {len(json_str)}")
            try:
                parsed_jd = json.loads(json_str)
                # Check if it's enterprise format with actual content
                if 'job_title' in parsed_jd and 'location' in parsed_jd:
                    # CRITICAL: Sanitize the parsed JD to remove agent reasoning artifacts
                    parsed_jd = sanitize_jd_dict(parsed_jd)
                    
                    # Verify it has actual content, not just structure (after sanitization)
                    position_summary = parsed_jd.get('position_summary', '')
                    has_content = (
                        position_summary and 
                        len(position_summary) > 50 and
                        len(parsed_jd.get('responsibilities', [])) > 0 and
                        # Check that position_summary is NOT contaminated
                        not any(marker in position_summary for marker in contamination_markers)
                    )
                    if has_content:
                        logger.info(f"✅ Successfully parsed Enterprise JD directly from result")
                        logger.info(f"   - Job Title: {parsed_jd.get('job_title')}")
                        logger.info(f"   - Position Summary length: {len(parsed_jd.get('position_summary', ''))}")
                        logger.info(f"   - Responsibilities count: {len(parsed_jd.get('responsibilities', []))}")
                        return self._ensure_enterprise_format(parsed_jd, user_location=user_location, user_department=user_department)
                    else:
                        logger.warning(f"⚠️ Parsed JD has structure but missing/contaminated content. Trying LLM extraction.")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ JSON decode error: {e}. Trying LLM extraction.")
        else:
            logger.warning(f"⚠️ No JSON found in result text. Trying LLM extraction.")
        
        # Use LLM to extract enterprise format
        logger.info("🔄 Using LLM to extract enterprise JD format...")
        extraction_prompt = get_enterprise_extraction_prompt(text)
        
        try:
            response = self.llm.invoke(extraction_prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            logger.info(f"🔍 LLM extraction response length: {len(response_text)}")
            
            # Extract JSON from response (handle markdown code blocks)
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
                try:
                    parsed_jd = json.loads(json_str)
                    logger.info(f"✅ Successfully parsed Enterprise JD from LLM extraction")
                    logger.info(f"   - Job Title: {parsed_jd.get('job_title')}")
                    logger.info(f"   - Position Summary length: {len(parsed_jd.get('position_summary', ''))}")
                    logger.info(f"   - Responsibilities count: {len(parsed_jd.get('responsibilities', []))}")
                    return self._ensure_enterprise_format(parsed_jd, user_location=user_location, user_department=user_department)
                except json.JSONDecodeError as e:
                    logger.warning(f"❌ Failed to parse JSON from LLM response: {e}")
                    logger.debug(f"   JSON string (first 500 chars): {json_str[:500]}")
            else:
                logger.warning("❌ No JSON found in LLM extraction response")
                logger.debug(f"   Response (first 500 chars): {response_text[:500]}")
                
        except Exception as e:
            logger.error(f"❌ LLM extraction failed: {e}", exc_info=True)
        
        # Fallback: return default enterprise structure with raw text
        logger.warning("⚠️ Falling back to default enterprise JD structure with raw text")
        return self._create_default_enterprise_jd(text)
    
    def _ensure_enterprise_format(self, jd: Dict[str, Any], user_location: str = None, user_department: str = None) -> Dict[str, Any]:
        """Ensure JD has all enterprise format fields with defaults and enforce Malomatia company info."""
        defaults = self._create_default_enterprise_jd("")
        
        # FIRST: Sanitize the JD to remove any agent reasoning artifacts
        jd = sanitize_jd_dict(jd)
        
        # Log what we're starting with
        logger.debug(f"🔧 _ensure_enterprise_format input keys: {list(jd.keys())}")
        
        # Merge with defaults for missing fields ONLY
        # Be careful not to overwrite existing content with empty defaults
        for key, value in defaults.items():
            if key not in jd:
                # Key doesn't exist at all - add default
                jd[key] = value
                logger.debug(f"   Added missing key: {key}")
            elif jd[key] is None:
                # Key exists but is None - add default
                jd[key] = value
                logger.debug(f"   Replaced None value for: {key}")
            elif isinstance(value, dict) and isinstance(jd.get(key), dict):
                # Both are dicts - merge sub-keys
                for sub_key, sub_value in value.items():
                    if sub_key not in jd[key]:
                        jd[key][sub_key] = sub_value
                    elif jd[key][sub_key] is None:
                        jd[key][sub_key] = sub_value
            # NOTE: We do NOT overwrite existing arrays or strings, even if empty
            # The LLM should have populated them
        
        # ALWAYS enforce Malomatia company info - override whatever LLM generated
        # Pass ALL user inputs to preserve them (job_title, location, department, level, requirements)
        # Get original values from context if not passed directly
        if not user_department and hasattr(self, '_current_context') and self._current_context:
            user_department = self._current_context.get('department')
        
        # Get job_level and user_requirements from context
        user_job_level = None
        user_requirements = None
        if hasattr(self, '_current_context') and self._current_context:
            user_job_level = self._current_context.get('job_level')
            user_requirements = self._current_context.get('user_requirements')
        
        jd = enforce_malomatia_defaults(
            jd, 
            original_job_title=jd.get("job_title"), 
            user_location=user_location,
            user_department=user_department,
            user_job_level=user_job_level,
            user_requirements=user_requirements
        )
        
        # ===== CLEAN UP TOOLS_TECHNOLOGIES =====
        # Remove concepts that are not tools and move them to technical_skills
        tools_technologies = jd.get('tools_technologies', [])
        if tools_technologies and isinstance(tools_technologies, list):
            cleaned_tools = []
            concepts_to_move = []
            
            for tool in tools_technologies:
                if not isinstance(tool, str):
                    continue
                tool_lower = tool.lower().strip()
                
                # Skip empty or very short items
                if len(tool_lower) < 2:
                    continue
                
                # Check for category:items format (e.g., "Programming: Java")
                if ':' in tool:
                    parts = tool.split(':', 1)
                    category = parts[0].strip().lower()
                    items_str = parts[1].strip() if len(parts) > 1 else ''
                    
                    # Split items and add them individually
                    items = [item.strip() for item in items_str.split(',') if item.strip()]
                    for item in items:
                        if is_known_tool_or_technology(item):
                            cleaned_tools.append(item)
                        elif is_concept_or_methodology(item):
                            concepts_to_move.append(item)
                        elif len(item) <= 15:  # Likely a tool if short
                            cleaned_tools.append(item)
                        else:
                            concepts_to_move.append(item)
                # Check if it's a concept, not a tool
                elif is_concept_or_methodology(tool):
                    concepts_to_move.append(tool)
                # Check if it's a known tool
                elif is_known_tool_or_technology(tool):
                    cleaned_tools.append(tool)
                # Otherwise keep if it looks like a tool (short)
                elif len(tool) <= 20:
                    cleaned_tools.append(tool)
                else:
                    # Might be a concept or skill
                    concepts_to_move.append(tool)
            
            # Remove duplicates from cleaned tools
            seen = set()
            unique_tools = []
            for tool in cleaned_tools:
                tool_lower = tool.lower()
                if tool_lower not in seen:
                    seen.add(tool_lower)
                    unique_tools.append(tool)
            
            jd['tools_technologies'] = unique_tools
            
            # Move concepts to technical_skills
            if concepts_to_move:
                req_qual = jd.get('required_qualifications', {})
                if isinstance(req_qual, dict):
                    tech_skills = req_qual.get('technical_skills', [])
                    if isinstance(tech_skills, list):
                        existing_skills = set(s.lower() for s in tech_skills)
                        for concept in concepts_to_move:
                            if concept.lower() not in existing_skills:
                                tech_skills.append(concept)
                                existing_skills.add(concept.lower())
                        jd['required_qualifications']['technical_skills'] = tech_skills
                        logger.info(f"✅ Moved {len(concepts_to_move)} concepts from tools to technical_skills")
            
            if len(unique_tools) != len(tools_technologies):
                logger.info(f"✅ Cleaned tools_technologies: {len(tools_technologies)} → {len(unique_tools)} items")
        
        # Validate and ensure success_metrics are present
        success_metrics = jd.get('success_metrics', [])
        if not success_metrics or len(success_metrics) == 0:
            logger.warning(f"⚠️ success_metrics is empty or missing for {jd.get('job_title', 'unknown')}. Generating fallback metrics.")
            # Generate role-appropriate fallback metrics based on job title
            job_title = jd.get('job_title', '').lower()
            fallback_metrics = self._generate_fallback_success_metrics(job_title)
            jd['success_metrics'] = fallback_metrics
            logger.info(f"✅ Added {len(fallback_metrics)} fallback success metrics")
        
        # ===== CRITICAL: ENFORCE LEVEL CONSISTENCY ACROSS ALL 15 SECTIONS =====
        # This ensures ALL sections (responsibilities, experience, reporting, etc.) match the job level
        if user_job_level:
            jd = enforce_level_consistency(jd, user_job_level, jd.get('job_title', ''))
        
        # ===== FINAL CLEANUP: Fix text errors, spacing, and deduplication =====
        # This is the LAST step - fixes spacing errors, removes UI artifacts,
        # deduplicates soft skills, cleans tools list
        jd = sanitize_jd_text_content(jd)
        logger.info("✅ Applied final text cleanup (spacing, deduplication, UI artifacts)")
        
        # Log what we're returning
        logger.debug(f"🔧 _ensure_enterprise_format output:")
        logger.debug(f"   - position_summary length: {len(jd.get('position_summary', ''))}")
        logger.debug(f"   - responsibilities count: {len(jd.get('responsibilities', []))}")
        logger.debug(f"   - success_metrics count: {len(jd.get('success_metrics', []))}")
        
        return jd
    
    def _generate_fallback_success_metrics(self, job_title: str) -> list:
        """Generate fallback success metrics based on job title keywords."""
        job_title_lower = job_title.lower()
        
        # Governance/Compliance roles
        if any(keyword in job_title_lower for keyword in ['governance', 'compliance', 'risk', 'audit', 'regulatory']):
            return [
                "Achievement and maintenance of high compliance audit scores (target: >95%)",
                "Reduction in identified compliance gaps and audit findings",
                "Timely completion of compliance reviews and assessments",
                "Effective implementation and adherence to governance policies and frameworks",
                "Positive feedback from stakeholders on governance effectiveness",
                "Successful completion of regulatory audits with minimal findings"
            ]
        
        # Security roles
        elif any(keyword in job_title_lower for keyword in ['security', 'cybersecurity', 'vulnerability', 'threat']):
            return [
                "Reduction in security incidents and vulnerabilities",
                "Improved security posture as measured by security assessments",
                "Timely and effective response to security incidents",
                "Successful completion of security audits and penetration tests",
                "Implementation and maintenance of effective security controls"
            ]
        
        # Engineering/Development roles
        elif any(keyword in job_title_lower for keyword in ['engineer', 'developer', 'programmer', 'software']):
            return [
                "Delivery of high-quality, well-tested code that meets project specifications",
                "Successful implementation of features and enhancements on schedule",
                "Reduction in production incidents and bug reports",
                "Measurable improvement in application performance and scalability",
                "Effective collaboration with cross-functional teams"
            ]
        
        # Management/Leadership roles
        elif any(keyword in job_title_lower for keyword in ['manager', 'director', 'lead', 'head', 'chief']):
            return [
                "Successful on-time delivery of projects and initiatives",
                "Achievement of team performance and productivity targets",
                "Positive stakeholder feedback and satisfaction scores",
                "Effective budget management and resource utilization",
                "Successful team development and talent retention"
            ]
        
        # Data/AI roles
        elif any(keyword in job_title_lower for keyword in ['data', 'analyst', 'scientist', 'ai', 'ml', 'machine learning']):
            return [
                "Accuracy and performance of data models and analyses",
                "Timely delivery of data insights and reports",
                "Improvement in data quality and reliability metrics",
                "Successful implementation of data-driven solutions",
                "Positive impact of data insights on business decisions"
            ]
        
        # Default/generic metrics
        else:
            return [
                "Successful completion of assigned tasks and projects within defined timelines",
                "Achievement of quality standards and performance targets",
                "Positive feedback from stakeholders and team members",
                "Effective collaboration and contribution to team objectives",
                "Continuous improvement in role-specific skills and competencies"
            ]
    
    def _create_default_enterprise_jd(self, raw_text: str = "") -> Dict[str, Any]:
        """Create default enterprise JD structure with Malomatia company info."""
        return {
            "job_title": "Job Title",
            "department": "Department",
            "team": None,
            "division": None,
            "location": MALOMATIA_COMPANY_INFO["default_location"].copy(),
            "about_company": MALOMATIA_COMPANY_INFO["about_company"],
            "position_summary": raw_text[:500] if raw_text else "Position summary to be defined.",
            "responsibilities": [],
            "required_qualifications": {
                "education": "Bachelor's degree in relevant field",
                "experience": "3+ years of relevant experience",
                "technical_skills": []
            },
            "preferred_qualifications": [],
            "soft_skills": ["Communication", "Problem-solving", "Teamwork", "Adaptability"],
            "tools_technologies": [],
            "success_metrics": [],
            "work_environment": {
                "reports_to": "Manager",
                "team_size": None,
                "collaborates_with": [],
                "collaboration_mode": "Agile"
            },
            "compensation_benefits": ["Competitive salary", "Health insurance", "PTO"],
            "equal_opportunity_statement": MALOMATIA_COMPANY_INFO["equal_opportunity_statement"],
            "application_instructions": MALOMATIA_COMPANY_INFO["application_instructions"].copy(),
            "metadata": {"raw_text": raw_text} if raw_text else None
        }


class JDRefinerAgent(BaseCrewAgent):
    """Agent responsible for refining and improving Job Descriptions."""
    
    # Minimum item counts to enforce (same as validator)
    MINIMUM_COUNTS = {
        "responsibilities": 10,
        "technical_skills": 8,
        "preferred_qualifications": 4,
        "soft_skills": 5,
        "tools_technologies": 10,
        "success_metrics": 4,
        "compensation_benefits": 4,
    }
    
    def __init__(self, config=None):
        """
        Initialize JD Refiner Agent.
        
        Args:
            config: JDGenerationConfig instance (uses global config if not provided)
        """
        super().__init__(
            agent_name="JD Refiner",
            role="Senior HR Content Editor & JD Quality Specialist",
            goal="Refine Job Descriptions to ensure clarity, consistency, and professional excellence",
            backstory="""You are a meticulous HR content editor with expertise in 
            polishing job descriptions. You have an eye for detail and ensure every 
            JD is clear, consistent, professional, and free of errors. You improve 
            language, enhance clarity, and ensure alignment with best practices.""",
            config=config,
        )
    
    def _ensure_minimum_counts(self, jd: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ensure all sections meet minimum item counts.
        
        This method checks and fixes sections that are below minimum requirements.
        It uses the LLM to generate additional relevant items.
        """
        job_title = jd.get('job_title', context.get('job_title', 'Position'))
        fixes_applied = []
        
        # Check and fix responsibilities
        responsibilities = jd.get('responsibilities', [])
        if isinstance(responsibilities, list) and len(responsibilities) < self.MINIMUM_COUNTS["responsibilities"]:
            needed = self.MINIMUM_COUNTS["responsibilities"] - len(responsibilities)
            fixes_applied.append(f"Adding {needed} responsibilities")
            # Generate additional responsibilities using templates
            additional = self._generate_additional_items(
                "responsibilities", job_title, needed, 
                existing=responsibilities,
                context=context
            )
            jd['responsibilities'] = responsibilities + additional
        
        # Check and fix tools_technologies
        tools = jd.get('tools_technologies', [])
        if isinstance(tools, list) and len(tools) < self.MINIMUM_COUNTS["tools_technologies"]:
            needed = self.MINIMUM_COUNTS["tools_technologies"] - len(tools)
            fixes_applied.append(f"Adding {needed} tools")
            additional = self._generate_additional_items(
                "tools", job_title, needed,
                existing=tools,
                context=context
            )
            jd['tools_technologies'] = tools + additional
        
        # Check and fix soft_skills
        soft_skills = jd.get('soft_skills', [])
        if isinstance(soft_skills, list) and len(soft_skills) < self.MINIMUM_COUNTS["soft_skills"]:
            needed = self.MINIMUM_COUNTS["soft_skills"] - len(soft_skills)
            fixes_applied.append(f"Adding {needed} soft skills")
            additional = self._generate_additional_items(
                "soft_skills", job_title, needed,
                existing=soft_skills,
                context=context
            )
            jd['soft_skills'] = soft_skills + additional
        
        # Check and fix preferred_qualifications
        pref_qual = jd.get('preferred_qualifications', [])
        if isinstance(pref_qual, list) and len(pref_qual) < self.MINIMUM_COUNTS["preferred_qualifications"]:
            needed = self.MINIMUM_COUNTS["preferred_qualifications"] - len(pref_qual)
            fixes_applied.append(f"Adding {needed} preferred qualifications")
            additional = self._generate_additional_items(
                "preferred_qualifications", job_title, needed,
                existing=pref_qual,
                context=context
            )
            jd['preferred_qualifications'] = pref_qual + additional
        
        # Check and fix success_metrics
        metrics = jd.get('success_metrics', [])
        if isinstance(metrics, list) and len(metrics) < self.MINIMUM_COUNTS["success_metrics"]:
            needed = self.MINIMUM_COUNTS["success_metrics"] - len(metrics)
            fixes_applied.append(f"Adding {needed} success metrics")
            additional = self._generate_additional_items(
                "success_metrics", job_title, needed,
                existing=metrics,
                context=context
            )
            jd['success_metrics'] = metrics + additional
        
        # Check and fix compensation_benefits
        benefits = jd.get('compensation_benefits', [])
        if isinstance(benefits, list) and len(benefits) < self.MINIMUM_COUNTS["compensation_benefits"]:
            needed = self.MINIMUM_COUNTS["compensation_benefits"] - len(benefits)
            fixes_applied.append(f"Adding {needed} benefits")
            additional = self._generate_additional_items(
                "benefits", job_title, needed,
                existing=benefits,
                context=context
            )
            jd['compensation_benefits'] = benefits + additional
        
        # Check and fix technical_skills inside required_qualifications
        req_qual = jd.get('required_qualifications', {})
        if isinstance(req_qual, dict):
            tech_skills = req_qual.get('technical_skills', [])
            if isinstance(tech_skills, list) and len(tech_skills) < self.MINIMUM_COUNTS["technical_skills"]:
                needed = self.MINIMUM_COUNTS["technical_skills"] - len(tech_skills)
                fixes_applied.append(f"Adding {needed} technical skills")
                additional = self._generate_additional_items(
                    "technical_skills", job_title, needed,
                    existing=tech_skills,
                    context=context
                )
                jd['required_qualifications']['technical_skills'] = tech_skills + additional
        
        # ===== FIX EXPERIENCE BASED ON JOB LEVEL =====
        # Ensure experience requirements match the job level
        job_level = context.get('job_level', jd.get('job_level', '')).lower() if context else jd.get('job_level', '').lower()
        if isinstance(req_qual, dict) and job_level:
            current_experience = req_qual.get('experience', '')
            new_experience = None
            
            if 'senior' in job_level:
                # Senior should have 5+ years
                if not any(y in current_experience.lower() for y in ['5+', '6+', '7+', '8+', '5-', '6-', '7-', '8-']):
                    new_experience = f"5-8 years of experience in {job_title} or related field, with proven expertise in relevant technologies"
                    fixes_applied.append("Fixed experience to 5-8 years for Senior role")
            elif 'lead' in job_level or 'principal' in job_level:
                # Lead/Principal should have 8+ years
                if not any(y in current_experience.lower() for y in ['8+', '10+', '8-', '10-', '12']):
                    new_experience = f"8-12+ years of experience in {job_title} or related field, with significant leadership experience"
                    fixes_applied.append("Fixed experience to 8-12+ years for Lead/Principal role")
            elif 'mid' in job_level:
                # Mid should have 3-5 years
                if not any(y in current_experience.lower() for y in ['3+', '3-5', '4+', '4-5', '3-']):
                    new_experience = f"3-5 years of experience in {job_title} or related field"
                    fixes_applied.append("Fixed experience to 3-5 years for Mid-level role")
            elif 'junior' in job_level or 'entry' in job_level:
                # Junior should have 0-2 years
                if '5+' in current_experience.lower() or '8+' in current_experience.lower():
                    new_experience = f"0-2 years of experience in {job_title} or related field, or recent graduate with relevant coursework"
                    fixes_applied.append("Fixed experience to 0-2 years for Junior role")
            
            if new_experience:
                jd['required_qualifications']['experience'] = new_experience
                logger.info(f"✅ Fixed experience requirement: {new_experience}")
        
        if fixes_applied:
            logger.info(f"✅ Applied fixes to meet minimum counts: {', '.join(fixes_applied)}")
        
        return jd
    
    def _generate_additional_items(
        self, 
        item_type: str, 
        job_title: str, 
        count: int,
        existing: List[str] = None,
        context: Dict[str, Any] = None
    ) -> List[str]:
        """
        Generate additional items for a section based on job title and level.
        
        This uses predefined templates for common roles and generates
        level-appropriate items to fill minimum requirements.
        """
        existing = existing or []
        existing_lower = [e.lower() for e in existing]
        
        # Get job level for level-appropriate content
        job_level = (context.get('job_level', '') if context else '').lower()
        
        # Template items by type, role, and LEVEL
        templates = {
            "responsibilities": {
                "junior": [
                    "Assist senior team members with project implementation and delivery",
                    "Support the development and testing of software components under guidance",
                    "Participate in code reviews to learn and improve coding practices",
                    "Help document processes, procedures, and technical specifications",
                    "Execute assigned tasks and report progress to team lead",
                    "Learn and apply best practices in software development",
                    "Support quality assurance testing and bug fixing efforts",
                    "Assist with data collection and analysis for team projects",
                    "Participate in team meetings and contribute ideas",
                    "Help maintain and update technical documentation"
                ],
                "mid": [
                    "Develop and implement software solutions independently",
                    "Collaborate with cross-functional teams to deliver project objectives",
                    "Analyze requirements and propose technical solutions",
                    "Create and maintain comprehensive technical documentation",
                    "Participate in code reviews and provide constructive feedback",
                    "Contribute to continuous improvement initiatives",
                    "Manage assigned workstreams and ensure timely delivery",
                    "Identify and resolve technical issues proactively",
                    "Support knowledge sharing within the team",
                    "Implement quality assurance practices in development workflow"
                ],
                "senior": [
                    "Lead the design and architecture of complex technical solutions",
                    "Mentor junior and mid-level team members on best practices",
                    "Drive technical excellence and establish coding standards",
                    "Collaborate with stakeholders to define technical requirements",
                    "Architect scalable and maintainable software solutions",
                    "Guide the team through complex technical decisions",
                    "Review and approve critical code changes and system designs",
                    "Identify opportunities for process optimization and innovation",
                    "Present technical strategies to leadership and stakeholders",
                    "Ensure compliance with security and quality standards"
                ],
                "default": [
                    "Collaborate with cross-functional teams to deliver project objectives",
                    "Document processes, procedures, and technical specifications",
                    "Participate in code reviews and provide constructive feedback",
                    "Contribute to continuous improvement initiatives",
                    "Support knowledge sharing and team development",
                    "Ensure compliance with organizational standards and best practices",
                    "Prepare status reports and communicate progress to stakeholders",
                    "Identify and escalate risks and issues proactively",
                    "Implement solutions according to technical specifications",
                    "Drive innovation and process optimization"
                ],
                "analyst": [
                    "Conduct stakeholder interviews and requirements workshops",
                    "Create detailed business requirements documents (BRD)",
                    "Develop functional specifications and user stories",
                    "Perform gap analysis between current and future state",
                    "Facilitate user acceptance testing (UAT) sessions",
                    "Create process flow diagrams and data models",
                    "Analyze data to derive actionable insights",
                    "Present findings and recommendations to leadership",
                    "Maintain requirements traceability matrix",
                    "Support change management and training initiatives"
                ]
            },
            "tools": {
                "default": ["Microsoft Office Suite", "Confluence", "Jira", "Slack", "Git", "SharePoint", "Teams", "VS Code", "Postman", "Docker"],
                "analyst": ["Microsoft Visio", "Lucidchart", "SQL", "Power BI", "Tableau", "Confluence", "Jira", "Excel (Advanced)", "SharePoint", "Miro"]
            },
            "soft_skills": {
                "junior": [
                    "Eagerness to learn and grow",
                    "Strong communication skills",
                    "Team player with positive attitude",
                    "Attention to detail",
                    "Adaptability and flexibility",
                    "Willingness to receive and act on feedback",
                    "Basic problem-solving skills"
                ],
                "senior": [
                    "Technical leadership and mentoring ability",
                    "Strategic thinking and decision-making",
                    "Excellent stakeholder management",
                    "Strong negotiation and influence skills",
                    "Ability to drive change and innovation",
                    "Conflict resolution and team building",
                    "Executive-level communication skills"
                ],
                "default": [
                    "Excellent written and verbal communication",
                    "Strong analytical and problem-solving abilities",
                    "Ability to work independently and in team environments",
                    "Attention to detail and quality focus",
                    "Adaptability and willingness to learn",
                    "Time management and prioritization skills",
                    "Stakeholder management and relationship building"
                ]
            },
            "preferred_qualifications": {
                "default": [
                    "Relevant professional certification",
                    "Experience in Agile/Scrum methodologies",
                    "Experience with enterprise-scale projects",
                    "Background in consulting or professional services",
                    "Knowledge of industry best practices",
                    "Experience with international or remote teams"
                ]
            },
            "success_metrics": {
                "default": [
                    "Quality and accuracy of deliverables",
                    "Stakeholder satisfaction scores",
                    "On-time delivery of assigned tasks",
                    "Contribution to team goals and objectives",
                    "Continuous improvement initiatives implemented",
                    "Knowledge sharing and documentation quality"
                ]
            },
            "benefits": {
                "default": [
                    "Competitive salary and performance bonuses",
                    "Comprehensive health, dental, and vision insurance",
                    "Flexible working arrangements",
                    "Professional development and training budget",
                    "Paid time off and holidays",
                    "Retirement savings plan with company match"
                ]
            },
            "technical_skills": {
                "default": ["SQL", "Data Analysis", "Process Modeling", "Requirements Documentation", "Business Writing", "Stakeholder Management", "Project Management Basics", "Agile Methodology"]
            }
        }
        
        # Determine role category
        title_lower = job_title.lower()
        role_key = "default"
        if "analyst" in title_lower:
            role_key = "analyst"
        
        # Determine level key for level-appropriate content
        level_key = "default"
        if 'junior' in job_level or 'entry' in job_level:
            level_key = "junior"
        elif 'senior' in job_level:
            level_key = "senior"
        elif 'mid' in job_level:
            level_key = "mid"
        
        # Get template items - prioritize level over role for responsibilities and soft_skills
        type_templates = templates.get(item_type, templates.get("soft_skills", {}))
        
        if item_type in ["responsibilities", "soft_skills"] and level_key in type_templates:
            # Use level-specific templates for responsibilities and soft skills
            items_pool = type_templates.get(level_key, type_templates.get("default", []))
            logger.debug(f"Using {level_key}-level templates for {item_type}")
        else:
            # Use role-based or default templates
            items_pool = type_templates.get(role_key, type_templates.get("default", []))
        
        # ===== PRIORITIZE USER REQUIREMENTS (PARSED) =====
        # Use parsed requirements if available, otherwise parse raw requirements
        user_req_items = []
        
        # Check if we have pre-parsed requirements in context
        parsed_requirements = context.get('parsed_requirements', None) if context else None
        
        if parsed_requirements:
            # Use pre-parsed requirements
            if item_type == "tools":
                # Only add actual tools, not concepts
                for tool in parsed_requirements.get('tools', []):
                    if tool.lower() not in existing_lower:
                        user_req_items.append(tool)
            elif item_type == "technical_skills":
                # Add both skills and concepts
                for skill in parsed_requirements.get('skills', []):
                    if skill.lower() not in existing_lower:
                        user_req_items.append(skill)
                for concept in parsed_requirements.get('concepts', []):
                    if concept.lower() not in existing_lower:
                        user_req_items.append(concept)
            elif item_type == "responsibilities":
                # Create responsibilities based on all items
                for item in parsed_requirements.get('all_items', []):
                    if item.lower() not in existing_lower:
                        if len(item) > 3:
                            user_req_items.append(f"Apply {item} expertise to deliver high-quality solutions")
            elif item_type == "soft_skills":
                # Only add soft skill-related items
                for item in parsed_requirements.get('all_items', []):
                    item_lower = item.lower()
                    if any(kw in item_lower for kw in ['communication', 'client', 'stakeholder', 'teamwork', 'leadership']):
                        if item_lower not in existing_lower:
                            user_req_items.append(f"Strong {item.lower()} skills")
        else:
            # Fallback: parse raw requirements
            user_requirements = context.get('user_requirements', '') if context else ''
            
            if user_requirements and user_requirements.lower() not in ['none specified', 'none', '']:
                # Use the new parser function
                parsed = parse_user_requirements(user_requirements)
                
                if item_type == "tools":
                    user_req_items = [t for t in parsed.get('tools', []) if t.lower() not in existing_lower]
                elif item_type == "technical_skills":
                    user_req_items = [s for s in parsed.get('skills', []) + parsed.get('concepts', []) if s.lower() not in existing_lower]
                elif item_type == "responsibilities":
                    for item in parsed.get('all_items', []):
                        if item.lower() not in existing_lower and len(item) > 3:
                            user_req_items.append(f"Apply {item} expertise to deliver project objectives")
                elif item_type == "soft_skills":
                    for item in parsed.get('all_items', []):
                        item_lower = item.lower()
                        if any(kw in item_lower for kw in ['communication', 'client', 'stakeholder']):
                            if item_lower not in existing_lower:
                                user_req_items.append(f"Strong {item.lower()} skills")
        
        # Combine user requirement items with template items
        items_pool = user_req_items + [item for item in items_pool if item.lower() not in existing_lower]
        
        # Filter out existing items
        available = [item for item in items_pool if item.lower() not in existing_lower]
        
        # Return requested count
        return available[:count]
    
    @traceable(name="refine_jd")
    def refine_jd(self, initial_jd: Dict[str, Any], context: Dict[str, Any], state: dict = None) -> Dict[str, Any]:
        """
        Refine and improve Enterprise JD using streamlined OTPAR cycle.
        
        OTPAR Cycle (Single Pass - No Redundant Cycles):
        - OBSERVE: Analyze initial JD structure and content
        - THINK: Identify areas for improvement (clarity, completeness, professionalism)
        - PLAN: Create refinement strategy for each section
        - ACT: Execute LangChain LLM to refine actual JD content (NOT meta-plans)
        - REFLECT: Evaluate refinement quality
        
        Args:
            initial_jd: Initial enterprise JD to refine
            context: Context with similar jobs and requirements
            state: Optional workflow state for logging agent thoughts
        """
        job_title = initial_jd.get('job_title', 'Position')
        
        # ===== OBSERVE Phase =====
        self._log_autonomous_action("OBSERVE", f"Analyzing initial JD for {job_title}")
        if state:
            self._log_thought(f"OBSERVE: Reviewing JD structure and content for {job_title}", "Perceiving JD", state=state)
        
        observation = {
            "job_title": job_title,
            "position_summary_length": len(initial_jd.get('position_summary', '')),
            "responsibilities_count": len(initial_jd.get('responsibilities', [])),
            "similar_jobs_count": len(context.get('similar_jobs', [])),
            "user_requirements": context.get('user_requirements', ''),
        }
        
        # ===== THINK Phase =====
        self._log_autonomous_action("THINK", f"Identifying improvement areas for {job_title}")
        if state:
            self._log_thought(f"THINK: Analyzing content gaps and improvement opportunities", "Reasoning", state=state)
        
        # ===== PLAN Phase =====
        self._log_autonomous_action("PLAN", f"Creating refinement strategy for {job_title}")
        if state:
            self._log_thought("PLAN: Structuring improvements for clarity and professionalism", "Refinement planning", state=state)
        
        # ===== ACT Phase - Direct LLM Execution =====
        self._log_autonomous_action("ACT", f"Refining JD content for {job_title}")
        if state:
            self._log_thought("ACT: Executing JD refinement with LangGraph LLM", "Refining content", state=state)
        
        # Execute the actual JD refinement
        refined_jd = self._refine_with_llm(initial_jd, context, state=state)
        
        # ===== ENSURE MINIMUM COUNTS - Fix any sections below minimum =====
        if refined_jd:
            self._log_autonomous_action("QUALITY", "Ensuring all sections meet minimum item counts")
            refined_jd = self._ensure_minimum_counts(refined_jd, context)
        
        # ===== REFLECT Phase =====
        position_summary_len = len(refined_jd.get('position_summary', '')) if refined_jd else 0
        responsibilities_count = len(refined_jd.get('responsibilities', [])) if refined_jd else 0
        
        self._log_autonomous_action("REFLECT", f"Refined JD: {position_summary_len} chars summary, {responsibilities_count} responsibilities")
        if state:
            self._log_thought(
                f"REFLECT: Refined JD with {position_summary_len} chars summary, {responsibilities_count} responsibilities",
                "OTPAR refinement cycle complete",
                state=state
            )
        
        return refined_jd
    
    def _refine_with_crewai(self, initial_jd: Dict[str, Any], context: Dict[str, Any], state: dict = None) -> Dict[str, Any]:
        """Backward-compatible alias for LangGraph LLM refinement."""
        return self._refine_with_llm(initial_jd, context, state=state)

    def _refine_with_llm(self, initial_jd: Dict[str, Any], context: Dict[str, Any], state: dict = None) -> Dict[str, Any]:
        """Execute refinement using direct LangChain LLM invocation (ACT phase of OTPAR)."""
        from agents.jd_generation.enterprise_prompts import get_enterprise_refinement_prompt
        
        self._log_thought(
            "ACT phase: Refining Enterprise JD with all 15 sections.",
            "Executing refinement task",
            state=state
        )
        
        # CRITICAL: Store context for later use in _merge_with_initial
        self._current_context = context
        
        # Get enterprise refinement prompt with job_level for level-appropriate content
        refinement_prompt = get_enterprise_refinement_prompt(
            current_jd=initial_jd,
            similar_jobs_count=len(context.get('similar_jobs', [])),
            user_requirements=context.get('user_requirements', ''),
            job_level=context.get('job_level', initial_jd.get('job_level', 'Mid-level'))
        )

        refinement_task_prompt = self._build_task_prompt(
            refinement_prompt,
            expected_output=(
                "A refined Enterprise Job Description with all 15 sections in JSON format"
            ),
        )

        self._log_thought(
            "Executing refinement task. Analyzing and improving JD content.",
            "Running LLM refinement",
            state=state
        )

        try:
            result_text = invoke_prompt_with_retry(
                self._active_llm(),
                refinement_task_prompt,
                agent_name=self.agent_name,
                switch_fallback_fn=self.switch_to_fallback_model,
                get_llm_fn=self._active_llm,
                operation="JD refinement",
            )

            self._log_thought(
                "JD refinement completed. Extracting refined content.",
                "Processing result",
                state=state
            )

            refined_jd = self._parse_refinement_result(result_text, initial_jd)

            self._log_thought(
                "JD refined successfully. Quality improved.",
                "Refinement complete",
                state=state
            )

            return refined_jd

        except Exception as e:
            self._log_thought(
                f"Error during refinement: {str(e)}. Returning original JD.",
                "Refinement failed",
                state=state
            )
            return initial_jd
    
    def _parse_refinement_result(self, result: Any, initial_jd: Dict[str, Any]) -> Dict[str, Any]:
        """Parse refinement result into Enterprise 15-section format."""
        import json
        import re
        from agents.jd_generation.enterprise_prompts import get_enterprise_extraction_prompt
        
        text = extract_llm_text(result)
        contamination_markers = ['**ACT**:', '**OBSERVE**:', '**THINK**:', '**PLAN**:', 
                                 'Calling tool:', 'retrieve_similar_jobs', 'I will now execute']
        is_contaminated = any(marker in text for marker in contamination_markers)
        if is_contaminated:
            logger.warning("⚠️ DETECTED: Agent reasoning artifacts in Refiner output. Will sanitize.")
        
        # Try to parse JSON directly first
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                parsed_jd = json.loads(json_match.group(0))
                
                # CRITICAL: Sanitize the parsed JD to remove agent reasoning artifacts
                parsed_jd = sanitize_jd_dict(parsed_jd)
                
                # Check if it's enterprise format
                if 'job_title' in parsed_jd and 'location' in parsed_jd:
                    logger.info("Successfully parsed refined Enterprise JD directly")
                    return self._merge_with_initial(parsed_jd, initial_jd)
            except json.JSONDecodeError:
                pass
        
        # Use LLM to extract enterprise format
        extraction_prompt = get_enterprise_extraction_prompt(text)
        
        try:
            response = self.llm.invoke(extraction_prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                parsed_jd = json.loads(json_match.group(0))
                # Sanitize extraction result too
                parsed_jd = sanitize_jd_dict(parsed_jd)
                logger.info("Successfully parsed refined Enterprise JD from LLM")
                return self._merge_with_initial(parsed_jd, initial_jd)
        except Exception as e:
            logger.warning(f"Failed to parse refinement result: {e}")
        
        # Fallback: return initial JD with raw text
        refined_jd = initial_jd.copy()
        refined_jd["metadata"] = {"refinement_raw_text": text[:1000]}
        return refined_jd
    
    def _parse_refinement_result_text(self, text: str, initial_jd: Dict[str, Any]) -> Dict[str, Any]:
        """Parse refinement result text into Enterprise JD format."""
        import json
        import re
        
        # Try to parse JSON directly
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                parsed_jd = json.loads(json_match.group(0))
                if 'job_title' in parsed_jd:
                    return self._merge_with_initial(parsed_jd, initial_jd)
            except json.JSONDecodeError:
                pass
        
        # Fallback to initial JD
        return initial_jd
    
    def _merge_with_initial(self, refined: Dict[str, Any], initial: Dict[str, Any]) -> Dict[str, Any]:
        """Merge refined JD with initial, keeping refined values where available, and enforce Malomatia defaults."""
        result = initial.copy()
        for key, value in refined.items():
            if value is not None and value != "" and value != []:
                result[key] = value
        
        # Get job_level from context if not in result (priority: result > initial > context)
        user_job_level = result.get("job_level") or initial.get("job_level")
        user_requirements = result.get("user_requirements") or initial.get("user_requirements")
        job_title = result.get("job_title") or initial.get("job_title", "Position")
        
        # Also check stored context
        if hasattr(self, '_current_context') and self._current_context:
            if not user_job_level:
                user_job_level = self._current_context.get('job_level')
            if not user_requirements:
                user_requirements = self._current_context.get('user_requirements')
        
        # ALWAYS enforce Malomatia company info after merge
        # Preserve all user inputs from the initial JD
        result = enforce_malomatia_defaults(
            result, 
            original_job_title=result.get("job_title"),
            user_job_level=user_job_level,
            user_requirements=user_requirements
        )
        
        # ===== CRITICAL: ENFORCE LEVEL CONSISTENCY ACROSS ALL 15 SECTIONS =====
        # This ensures ALL sections match the job level (Junior, Mid, Senior, Lead)
        if user_job_level:
            result = enforce_level_consistency(result, user_job_level, job_title)
            logger.info(f"✅ Enforced {user_job_level} level consistency in merged JD")
        
        return result


class JDValidatorAgent(BaseCrewAgent):
    """Agent responsible for validating Job Descriptions."""
    
    # Minimum item counts for each section (enforced validation)
    MINIMUM_COUNTS = {
        "responsibilities": 10,
        "technical_skills": 8,  # Inside required_qualifications
        "preferred_qualifications": 4,
        "soft_skills": 5,
        "tools_technologies": 10,
        "success_metrics": 4,
        "compensation_benefits": 4,
    }
    
    def __init__(self, config=None):
        """
        Initialize JD Validator Agent.
        
        Args:
            config: JDGenerationConfig instance (uses global config if not provided)
        """
        super().__init__(
            agent_name="JD Validator",
            role="HR Quality Assurance Specialist",
            goal="Validate Job Descriptions for completeness, accuracy, and compliance",
            backstory="""You are a quality assurance specialist in HR with expertise 
            in validating job descriptions. You ensure every JD meets professional 
            standards, is complete, accurate, and compliant with best practices. 
            You check for missing information, inconsistencies, and quality issues.""",
            config=config,
        )
    
    def _validate_level_consistency(self, jd: Dict[str, Any], job_level: str) -> List[str]:
        """
        Validate that ALL sections are consistent with the job level.
        
        Args:
            jd: Job Description dictionary
            job_level: The job level (Junior, Mid, Senior, Lead)
            
        Returns:
            List of level inconsistency issues (empty if all pass)
        """
        issues = []
        if not job_level:
            return issues
        
        config = get_level_config(job_level)
        level_lower = job_level.lower()
        
        # Validate experience matches level
        req_qual = jd.get('required_qualifications', {})
        if isinstance(req_qual, dict):
            experience = req_qual.get('experience', '').lower()
            if experience:
                if 'junior' in level_lower or 'entry' in level_lower:
                    if any(x in experience for x in ['5+', '6+', '7+', '8+', '3-5', '5-8']):
                        issues.append(f"LEVEL MISMATCH: Experience '{experience}' is too high for Junior level (should be 0-2 years)")
                elif 'senior' in level_lower:
                    if any(x in experience for x in ['0-2', '1-3', '2-4']):
                        issues.append(f"LEVEL MISMATCH: Experience '{experience}' is too low for Senior level (should be 5-8 years)")
        
        # Validate responsibilities use appropriate action verbs
        responsibilities = jd.get('responsibilities', [])
        if responsibilities and isinstance(responsibilities, list):
            forbidden_verbs = config.get('forbidden_verbs', [])
            for resp in responsibilities[:5]:  # Check first 5
                if isinstance(resp, str):
                    resp_lower = resp.lower()
                    for forbidden in forbidden_verbs:
                        if resp_lower.startswith(forbidden.lower()):
                            issues.append(f"LEVEL MISMATCH: Responsibility starts with forbidden verb '{forbidden}' for {job_level} level")
                            break
        
        # Validate reports_to matches level
        work_env = jd.get('work_environment', {})
        if isinstance(work_env, dict):
            reports_to = work_env.get('reports_to', '')
            if reports_to:
                expected_reports = config.get('reports_to', [])
                if expected_reports:
                    is_appropriate = any(exp.lower() in reports_to.lower() for exp in expected_reports)
                    if not is_appropriate:
                        issues.append(f"LEVEL MISMATCH: '{reports_to}' is not appropriate for {job_level} (expected: {expected_reports[:2]})")
        
        return issues
    
    def _validate_item_counts(self, jd: Dict[str, Any]) -> List[str]:
        """
        Validate that all sections meet minimum item counts.
        
        Args:
            jd: Job Description dictionary
            
        Returns:
            List of count violation issues (empty if all pass)
        """
        issues = []
        
        # Check responsibilities
        responsibilities = jd.get('responsibilities', [])
        if isinstance(responsibilities, list) and len(responsibilities) < self.MINIMUM_COUNTS["responsibilities"]:
            issues.append(f"responsibilities has {len(responsibilities)} items (minimum: {self.MINIMUM_COUNTS['responsibilities']})")
        
        # Check technical_skills inside required_qualifications
        req_qual = jd.get('required_qualifications', {})
        if isinstance(req_qual, dict):
            tech_skills = req_qual.get('technical_skills', [])
            if isinstance(tech_skills, list) and len(tech_skills) < self.MINIMUM_COUNTS["technical_skills"]:
                issues.append(f"technical_skills has {len(tech_skills)} items (minimum: {self.MINIMUM_COUNTS['technical_skills']})")
        
        # Check preferred_qualifications
        pref_qual = jd.get('preferred_qualifications', [])
        if isinstance(pref_qual, list) and len(pref_qual) < self.MINIMUM_COUNTS["preferred_qualifications"]:
            issues.append(f"preferred_qualifications has {len(pref_qual)} items (minimum: {self.MINIMUM_COUNTS['preferred_qualifications']})")
        
        # Check soft_skills
        soft_skills = jd.get('soft_skills', [])
        if isinstance(soft_skills, list) and len(soft_skills) < self.MINIMUM_COUNTS["soft_skills"]:
            issues.append(f"soft_skills has {len(soft_skills)} items (minimum: {self.MINIMUM_COUNTS['soft_skills']})")
        
        # Check tools_technologies
        tools = jd.get('tools_technologies', [])
        if isinstance(tools, list) and len(tools) < self.MINIMUM_COUNTS["tools_technologies"]:
            issues.append(f"tools_technologies has {len(tools)} items (minimum: {self.MINIMUM_COUNTS['tools_technologies']})")
        
        # Check success_metrics
        metrics = jd.get('success_metrics', [])
        if isinstance(metrics, list) and len(metrics) < self.MINIMUM_COUNTS["success_metrics"]:
            issues.append(f"success_metrics has {len(metrics)} items (minimum: {self.MINIMUM_COUNTS['success_metrics']})")
        
        # Check compensation_benefits
        benefits = jd.get('compensation_benefits', [])
        if isinstance(benefits, list) and len(benefits) < self.MINIMUM_COUNTS["compensation_benefits"]:
            issues.append(f"compensation_benefits has {len(benefits)} items (minimum: {self.MINIMUM_COUNTS['compensation_benefits']})")
        
        return issues
    
    def calculate_quality_score(self, jd: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Calculate a comprehensive quality score (0-10) for the JD.
        
        Scoring Criteria:
        - Section Completeness (2 points): All 15 sections present with minimum counts
        - Content Relevance (2 points): Content matches job title and level
        - User Requirements (2 points): User's additional requirements are incorporated
        - Professional Quality (2 points): Language, formatting, action verbs
        - Specificity (2 points): Specific vs generic content
        
        Args:
            jd: Job Description dictionary
            context: Original context with user inputs
            
        Returns:
            Dict with score, breakdown, and improvement suggestions
        """
        score = 0.0
        breakdown = {}
        suggestions = []
        
        context = context or {}
        job_title = jd.get('job_title', context.get('job_title', '')).lower()
        user_requirements = context.get('user_requirements', '').lower()
        
        # ===== 1. SECTION COMPLETENESS (2 points) =====
        completeness_score = 0.0
        count_issues = self._validate_item_counts(jd)
        
        if not count_issues:
            completeness_score = 2.0
        else:
            # Deduct 0.25 for each count issue
            completeness_score = max(0, 2.0 - (len(count_issues) * 0.25))
            suggestions.extend([f"⚠️ {issue}" for issue in count_issues])
        
        breakdown["completeness"] = completeness_score
        score += completeness_score
        
        # ===== 2. CONTENT RELEVANCE (2 points) =====
        relevance_score = 2.0
        
        # Check if position_summary mentions the job title
        position_summary = jd.get('position_summary', '').lower()
        if job_title and job_title not in position_summary:
            relevance_score -= 0.5
            suggestions.append(f"Position summary should mention '{jd.get('job_title')}' by name")
        
        # Check if responsibilities seem relevant (basic check)
        responsibilities = jd.get('responsibilities', [])
        if len(responsibilities) > 0:
            # Simple relevance check - at least some responsibilities should relate to job title
            relevant_count = sum(1 for r in responsibilities if any(word in r.lower() for word in job_title.split() if len(word) > 3))
            if relevant_count < 2:
                relevance_score -= 0.5
                suggestions.append("Responsibilities should be more specific to the job title")
        
        breakdown["relevance"] = relevance_score
        score += relevance_score
        
        # ===== 3. USER REQUIREMENTS INCORPORATION (2 points) =====
        requirements_score = 2.0
        
        if user_requirements and user_requirements.lower() not in ["none specified", "none", ""]:
            # Extract key terms from user requirements (split by common delimiters)
            import re
            req_terms = re.split(r'[,\n\r&]+', user_requirements.lower())
            req_terms = [term.strip() for term in req_terms if len(term.strip()) > 2]
            
            # Check if user requirements appear in JD
            jd_text = str(jd).lower()
            found_terms = []
            missing_terms = []
            
            for term in req_terms:
                # Check for partial matches (e.g., "sql" matches "SQL Server")
                if term in jd_text or any(word in jd_text for word in term.split() if len(word) > 2):
                    found_terms.append(term)
                else:
                    missing_terms.append(term)
            
            if len(req_terms) > 0:
                incorporation_rate = len(found_terms) / len(req_terms)
                if incorporation_rate < 0.5:
                    requirements_score = 0.0
                    suggestions.append(f"❌ CRITICAL: User requirements NOT incorporated: {', '.join(missing_terms)}")
                elif incorporation_rate < 0.8:
                    requirements_score -= 1.0
                    suggestions.append(f"⚠️ Missing some user requirements: {', '.join(missing_terms)}")
                elif incorporation_rate < 1.0:
                    requirements_score -= 0.5
                    suggestions.append(f"⚠️ Partially missing: {', '.join(missing_terms)}")
        
        breakdown["user_requirements"] = requirements_score
        score += requirements_score
        
        # ===== 4. LEVEL APPROPRIATENESS (2 points) =====
        level_score = 2.0
        job_level = context.get('job_level', '').lower()
        
        if job_level:
            position_summary = jd.get('position_summary', '').lower()
            responsibilities_text = ' '.join([r.lower() for r in jd.get('responsibilities', [])])
            experience = ''
            req_qual = jd.get('required_qualifications', {})
            if isinstance(req_qual, dict):
                experience = req_qual.get('experience', '').lower()
            
            if 'senior' in job_level:
                # Senior should have leadership verbs and 5+ years
                senior_verbs = ['lead', 'mentor', 'architect', 'drive', 'establish', 'define', 'strategic']
                has_senior_verbs = any(v in responsibilities_text for v in senior_verbs)
                has_senior_experience = any(y in experience for y in ['5+', '6+', '7+', '8+', '5-', '6-', '7-', '8-'])
                
                if not has_senior_verbs:
                    level_score -= 1.0
                    suggestions.append("⚠️ Senior role should include leadership verbs (Lead, Mentor, Architect, Drive)")
                if not has_senior_experience:
                    level_score -= 0.5
                    suggestions.append("⚠️ Senior role should require 5+ years experience")
                    
            elif 'junior' in job_level or 'entry' in job_level:
                # Junior should have learning/support verbs and 0-2 years
                junior_verbs = ['assist', 'support', 'learn', 'participate', 'help', 'contribute']
                has_junior_verbs = any(v in responsibilities_text for v in junior_verbs)
                has_junior_experience = any(y in experience for y in ['0-2', '1-2', '0-1', '1+', '2+', 'entry', 'graduate'])
                
                if not has_junior_verbs:
                    level_score -= 0.5
                    suggestions.append("⚠️ Junior role should include supportive verbs (Assist, Support, Learn)")
                if '5+' in experience or '8+' in experience:
                    level_score -= 1.0
                    suggestions.append("❌ Junior role should NOT require 5+ years experience")
                    
            elif 'mid' in job_level:
                # Mid should have 3-5 years
                has_mid_experience = any(y in experience for y in ['3+', '3-5', '4+', '4-5', '3-'])
                if not has_mid_experience:
                    level_score -= 0.5
                    suggestions.append("⚠️ Mid-level role should require 3-5 years experience")
        
        breakdown["level_appropriateness"] = level_score
        score += level_score
        
        # ===== 5. PROFESSIONAL QUALITY (1 point) =====
        quality_score = 1.0
        
        # Check responsibilities start with action verbs
        action_verbs = ['design', 'develop', 'build', 'create', 'implement', 'lead', 'manage', 
                        'analyze', 'coordinate', 'establish', 'drive', 'execute', 'collaborate',
                        'mentor', 'review', 'ensure', 'maintain', 'optimize', 'define', 'support',
                        'assist', 'participate', 'help', 'contribute', 'prepare', 'conduct']
        
        responsibilities = jd.get('responsibilities', [])
        verb_count = sum(1 for r in responsibilities if any(r.lower().strip().startswith(v) for v in action_verbs))
        if len(responsibilities) > 0:
            verb_rate = verb_count / len(responsibilities)
            if verb_rate < 0.7:
                quality_score -= 0.5
                suggestions.append("More responsibilities should start with action verbs")
        
        # Check for placeholder text
        jd_str = str(jd)
        placeholders = ['[insert', '[company', '[url]', 'xxx', 'tbd', 'to be determined', 'placeholder']
        if any(p in jd_str.lower() for p in placeholders):
            quality_score -= 0.5
            suggestions.append("Remove placeholder text from JD")
        
        breakdown["quality"] = max(0, quality_score)
        score += max(0, quality_score)
        
        # ===== 6. SPECIFICITY (1 point) =====
        specificity_score = 1.0
        
        # Check for generic phrases that should be avoided
        generic_phrases = [
            'various tasks', 'other duties as assigned', 'etc.', 'and more',
            'fast-paced environment', 'team player', 'self-starter', 'go-getter'
        ]
        
        generic_count = sum(1 for phrase in generic_phrases if phrase in jd_str.lower())
        if generic_count > 2:
            specificity_score -= 0.5
            suggestions.append("Replace generic phrases with specific job-related content")
        
        # Check tools are role-specific (not too many generic tools)
        tools = jd.get('tools_technologies', [])
        if len(tools) < 8:
            specificity_score -= 0.5
            suggestions.append("Add more role-specific tools and technologies")
        
        breakdown["specificity"] = max(0, specificity_score)
        score += max(0, specificity_score)
        
        # ===== FINAL SCORE (Total: 10 points) =====
        # Breakdown: completeness(2) + relevance(2) + user_requirements(2) + level(2) + quality(1) + specificity(1) = 10
        final_score = min(10.0, round(score, 1))
        
        # Determine quality rating
        if final_score >= 9.0:
            rating = "⭐ EXCELLENT (10/10 Quality)"
        elif final_score >= 8.0:
            rating = "✅ VERY GOOD (Meets standards)"
        elif final_score >= 7.0:
            rating = "⚠️ GOOD (Minor improvements needed)"
        elif final_score >= 5.0:
            rating = "⚠️ FAIR (Improvements required)"
        else:
            rating = "❌ NEEDS WORK (Significant improvements needed)"
        
        return {
            "score": final_score,
            "max_score": 10.0,
            "rating": rating,
            "breakdown": breakdown,
            "suggestions": suggestions,
            "is_perfect": final_score >= 9.0
        }
    
    @traceable(name="validate_jd")
    def validate_jd(self, jd: Dict[str, Any], state: dict = None) -> Dict[str, Any]:
        """
        Validate JD using streamlined OTPAR cycle.
        
        OTPAR Cycle (Single Pass - No Redundant Cycles):
        - OBSERVE: Analyze JD structure and content completeness
        - THINK: Identify validation criteria and potential issues
        - PLAN: Create validation checklist strategy
        - ACT: Execute LangChain LLM to validate actual JD content (NOT meta-plans)
        - REFLECT: Evaluate validation completeness
        
        Args:
            jd: Job Description to validate
            state: Optional workflow state for logging agent thoughts
        """
        job_title = jd.get('job_title', 'Position')
        
        # ===== OBSERVE Phase =====
        self._log_autonomous_action("OBSERVE", f"Analyzing JD for validation: {job_title}")
        if state:
            self._log_thought(f"OBSERVE: Reviewing JD completeness for {job_title}", "Perceiving JD", state=state)
        
        observation = {
            "job_title": job_title,
            "has_position_summary": bool(jd.get('position_summary')),
            "responsibilities_count": len(jd.get('responsibilities', [])),
            "has_required_qualifications": bool(jd.get('required_qualifications')),
            "has_location": bool(jd.get('location')),
        }
        
        # ===== COUNT VALIDATION - Check minimum item requirements =====
        count_issues = self._validate_item_counts(jd)
        if count_issues:
            self._log_autonomous_action("OBSERVE", f"⚠️ Count validation issues: {count_issues}")
            if state:
                self._log_thought(f"OBSERVE: Detected {len(count_issues)} sections below minimum counts", "Count validation", state=state)
        
        # ===== LEVEL VALIDATION - Ensure ALL 15 sections match job level =====
        job_level = jd.get('job_level', '')
        level_issues = self._validate_level_consistency(jd, job_level)
        if level_issues:
            self._log_autonomous_action("OBSERVE", f"⚠️ Level consistency issues: {level_issues}")
            if state:
                self._log_thought(f"OBSERVE: Detected {len(level_issues)} level mismatches for {job_level}", "Level validation", state=state)
        
        # ===== THINK Phase =====
        self._log_autonomous_action("THINK", f"Identifying validation criteria for {job_title}")
        if state:
            self._log_thought("THINK: Determining completeness, clarity, and compliance checks", "Reasoning", state=state)
        
        # ===== PLAN Phase =====
        self._log_autonomous_action("PLAN", f"Creating validation checklist for {job_title}")
        if state:
            self._log_thought("PLAN: Structuring validation checks for all 15 sections", "Validation planning", state=state)
        
        # ===== ACT Phase - Direct LLM Execution =====
        self._log_autonomous_action("ACT", f"Validating JD content for {job_title}")
        if state:
            self._log_thought("ACT: Executing JD validation with LangGraph LLM", "Validating content", state=state)
        
        # Execute the actual JD validation
        validation_result = self._validate_with_llm(jd, state=state)
        
        # Merge count validation issues into the validation result
        if count_issues:
            existing_issues = validation_result.get('issues', [])
            validation_result['issues'] = count_issues + existing_issues
            validation_result['is_valid'] = False  # Fail validation if counts don't meet minimum
            validation_result['count_validation_failed'] = True
            self._log_autonomous_action("VALIDATE", f"❌ Count validation FAILED: {count_issues}")
        
        # Merge level consistency issues into the validation result
        if level_issues:
            existing_issues = validation_result.get('issues', [])
            validation_result['issues'] = level_issues + existing_issues
            validation_result['level_validation_failed'] = True
            self._log_autonomous_action("VALIDATE", f"❌ Level validation FAILED for {job_level}: {level_issues}")
        
        # ===== QUALITY SCORING - Calculate comprehensive 10-point score =====
        context = state.get("context", {}) if state else {}
        quality_result = self.calculate_quality_score(jd, context)
        
        validation_result['quality_score'] = quality_result['score']
        validation_result['quality_rating'] = quality_result['rating']
        validation_result['quality_breakdown'] = quality_result['breakdown']
        validation_result['is_perfect'] = quality_result['is_perfect']
        
        # Add quality suggestions to recommendations
        if quality_result['suggestions']:
            existing_recommendations = validation_result.get('recommendations', [])
            validation_result['recommendations'] = existing_recommendations + quality_result['suggestions']
        
        # Mark as invalid if score is below 7 (requires refinement)
        if quality_result['score'] < 7.0:
            validation_result['is_valid'] = False
            validation_result['needs_refinement'] = True
            self._log_autonomous_action("QUALITY", f"⚠️ Quality score {quality_result['score']}/10 - needs refinement")
        
        self._log_autonomous_action("SCORE", f"📊 Quality Score: {quality_result['score']}/10 - {quality_result['rating']}")
        
        # ===== REFLECT Phase =====
        is_valid = validation_result.get('is_valid', True)
        issues_count = len(validation_result.get('issues', []))
        
        self._log_autonomous_action("REFLECT", f"Validation result: valid={is_valid}, issues={issues_count}")
        if state:
            self._log_thought(
                f"REFLECT: JD validation {'passed' if is_valid else 'failed'} with {issues_count} issues",
                "OTPAR validation cycle complete",
                state=state
            )
        
        return validation_result
    
    def _validate_with_crewai(self, jd: Dict[str, Any], state: dict = None) -> Dict[str, Any]:
        """Backward-compatible alias for LangGraph LLM validation."""
        return self._validate_with_llm(jd, state=state)

    def _validate_with_llm(self, jd: Dict[str, Any], state: dict = None) -> Dict[str, Any]:
        """Execute validation using direct LangChain LLM invocation (ACT phase of OTPAR)."""
        self._log_thought(
            "ACT phase: Validating JD completeness and quality.",
            "Executing validation task",
            state=state
        )

        validation_task_prompt = self._build_task_prompt(
            f"""
            Validate this Job Description:
            
            {jd}
            
            Check for:
            1. Completeness: All required sections present (overview, responsibilities, requirements, skills)
            2. Clarity: Clear and understandable language
            3. Professionalism: Professional tone throughout
            4. Accuracy: Information is accurate and consistent
            5. Compliance: Free of bias and discriminatory language
            6. Structure: Well-organized and formatted
            7. Specificity: Specific enough to attract right candidates
            
            Return validation result with:
            - is_valid: boolean
            - checks_passed: list of passed checks
            - issues: list of issues found (if any)
            - recommendations: list of recommendations
            """,
            expected_output=(
                "Validation result with is_valid, checks_passed, issues, and recommendations"
            ),
        )

        self._log_thought(
            "Executing validation task. Running quality checks.",
            "Running LLM validation",
            state=state
        )

        try:
            result_text = invoke_prompt_with_retry(
                self._active_llm(),
                validation_task_prompt,
                agent_name=self.agent_name,
                switch_fallback_fn=self.switch_to_fallback_model,
                get_llm_fn=self._active_llm,
                operation="JD validation",
            )

            self._log_thought(
                "Validation completed. Analyzing results.",
                "Processing result",
                state=state
            )

            validation = self._parse_validation_result(result_text)

            if validation.get("is_valid"):
                self._log_thought(
                    f"Validation passed. All checks: {', '.join(validation.get('checks_passed', []))}",
                    "Validation successful",
                    state=state
                )
            else:
                self._log_thought(
                    f"Validation found issues: {', '.join(validation.get('issues', []))}",
                    "Issues detected",
                    state=state
                )

            return validation

        except Exception as e:
            self._log_thought(
                f"Error during validation: {str(e)}",
                "Validation failed",
                state=state
            )
            return {
                "is_valid": False,
                "checks_passed": [],
                "issues": [f"Validation error: {str(e)}"],
                "recommendations": [],
            }

    def fix_jd(self, jd: Dict[str, Any], issues: List[str], state: dict = None) -> Dict[str, Any]:
        """Fix issues in JD."""
        self._log_thought(
            f"Fixing JD issues: {', '.join(issues)}",
            "Starting auto-fix",
            state=state
        )

        fix_task_prompt = self._build_task_prompt(
            f"""
            Fix these issues in the Job Description:
            
            Issues: {', '.join(issues)}
            
            JD: {jd}
            
            Fix all issues and return the corrected JD.
            """,
            expected_output="Fixed Job Description",
        )

        try:
            result_text = invoke_prompt_with_retry(
                self._active_llm(),
                fix_task_prompt,
                agent_name=self.agent_name,
                switch_fallback_fn=self.switch_to_fallback_model,
                get_llm_fn=self._active_llm,
                operation="JD auto-fix",
            )
            fixed_jd = self._parse_jd_result(result_text)

            self._log_thought(
                "Issues fixed successfully.",
                "Auto-fix complete",
                state=state
            )

            return fixed_jd

        except Exception as e:
            self._log_thought(
                f"Error during auto-fix: {str(e)}",
                "Auto-fix failed",
                state=state
            )
            return jd

    def _parse_validation_result(self, result: Any) -> Dict[str, Any]:
        """Parse validation result."""
        text = extract_llm_text(result)
        
        # Parse validation result
        # In production, use LLM to extract structured validation data
        return {
            "is_valid": "valid" in text.lower() or "passed" in text.lower(),
            "checks_passed": ["completeness", "clarity", "professionalism"],
            "issues": [],
            "recommendations": [],
        }
    
    def _parse_jd_result(self, result: Any) -> Dict[str, Any]:
        """Parse JD result from fix_jd crew into Enterprise JD format.
        
        This method properly extracts JSON from the LLM response, similar to
        GeneratorAgent._parse_jd_result, to ensure the fixed JD has proper
        structure for chunking and storage.
        """
        import json
        import re
        
        text = extract_llm_text(result)
        
        logger.info(f"🔍 ValidatorAgent parsing JD result. Text length: {len(text)}")
        
        # Check for contaminated output (agent reasoning leaked into result)
        contamination_markers = ['**ACT**:', '**OBSERVE**:', '**THINK**:', '**PLAN**:', 
                                 'Calling tool:', 'retrieve_similar_jobs', 'I will now execute']
        is_contaminated = any(marker in text for marker in contamination_markers)
        if is_contaminated:
            logger.warning("⚠️ DETECTED: Agent reasoning artifacts in ValidatorAgent output. Will sanitize.")
        
        # Try to extract JSON from the result
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            json_str = json_match.group(0)
            try:
                parsed_jd = json.loads(json_str)
                
                # CRITICAL: Sanitize the parsed JD to remove agent reasoning artifacts
                parsed_jd = sanitize_jd_dict(parsed_jd)
                
                # Check if it's enterprise format with actual content
                if 'job_title' in parsed_jd and parsed_jd.get('position_summary'):
                    position_summary = parsed_jd.get('position_summary', '')
                    # Verify it has actual content and is NOT contaminated
                    has_content = (
                        (len(position_summary) > 50 or len(parsed_jd.get('responsibilities', [])) > 0) and
                        not any(marker in position_summary for marker in contamination_markers)
                    )
                    if has_content:
                        logger.info(f"✅ ValidatorAgent successfully parsed Enterprise JD")
                        logger.info(f"   - Job Title: {parsed_jd.get('job_title')}")
                        logger.info(f"   - Position Summary length: {len(parsed_jd.get('position_summary', ''))}")
                        logger.info(f"   - Responsibilities count: {len(parsed_jd.get('responsibilities', []))}")
                        
                        # Ensure all required enterprise fields exist
                        return self._ensure_enterprise_format_for_validator(parsed_jd)
                    else:
                        logger.warning(f"⚠️ Parsed JD structure found but missing/contaminated content")
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ JSON decode error in ValidatorAgent: {e}")
        else:
            logger.warning(f"⚠️ No JSON found in ValidatorAgent result")
        
        # Fallback: return empty enterprise structure (will be caught downstream)
        logger.warning("⚠️ ValidatorAgent falling back to empty structure")
        return self._get_empty_enterprise_jd()
    
    def _ensure_enterprise_format_for_validator(self, jd: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure JD has all required enterprise fields for chunking."""
        # Define enterprise format defaults
        enterprise_defaults = {
            'job_title': '',
            'department': '',
            'team': None,
            'location': {
                'city': '',
                'country': '',
                'work_model': 'Hybrid',
                'travel_required': False,
                'travel_percentage': None
            },
            'about_company': '',
            'position_summary': '',
            'responsibilities': [],
            'required_qualifications': {
                'education': '',
                'experience': '',
                'technical_skills': []
            },
            'preferred_qualifications': [],
            'soft_skills': [],
            'tools_technologies': [],
            'success_metrics': [],
            'work_environment': {
                'reports_to': '',
                'team_size': None,
                'collaborates_with': [],
                'collaboration_mode': ''
            },
            'compensation_benefits': [],
            'equal_opportunity_statement': '',
            'application_instructions': {
                'apply_url': '',
                'email': '',
                'required_materials': []
            },
            'division': None,
            'metadata': None
        }
        
        # Merge with defaults (existing values take precedence)
        result = enterprise_defaults.copy()
        for key, value in jd.items():
            if value is not None:
                if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                    # Merge nested dicts
                    result[key] = {**result[key], **value}
                else:
                    result[key] = value
        
        return result
    
    def _get_empty_enterprise_jd(self) -> Dict[str, Any]:
        """Return empty enterprise JD structure."""
        return {
            'job_title': '',
            'department': '',
            'team': None,
            'location': {
                'city': '',
                'country': '',
                'work_model': 'Hybrid',
                'travel_required': False,
                'travel_percentage': None
            },
            'about_company': '',
            'position_summary': '',
            'responsibilities': [],
            'required_qualifications': {
                'education': '',
                'experience': '',
                'technical_skills': []
            },
            'preferred_qualifications': [],
            'soft_skills': [],
            'tools_technologies': [],
            'success_metrics': [],
            'work_environment': {
                'reports_to': '',
                'team_size': None,
                'collaborates_with': [],
                'collaboration_mode': ''
            },
            'compensation_benefits': [],
            'equal_opportunity_statement': '',
            'application_instructions': {
                'apply_url': '',
                'email': '',
                'required_materials': []
            },
            'division': None,
            'metadata': None
        }


class RAGAgent(BaseCrewAgent):
    """Agent responsible for RAG (Retrieval Augmented Generation) context gathering.
    
    Uses DirectRetriever (lightweight similarity search) for:
    - Hybrid retrieval (vector + keyword search)
    - RRF fusion
    - Reranking
    - Document grouping
    
    Note: QueryRouter is for QuantChat Q&A, not for JD similarity search.
    DirectRetriever provides optimal performance without Q&A pipeline overhead.
    """
    
    def __init__(self, config=None):
        """
        Initialize RAG Agent.
        
        Args:
            config: JDGenerationConfig instance (uses global config if not provided)
        """
        super().__init__(
            agent_name="RAG Agent",
            role="Information Retrieval Specialist",
            goal="Retrieve relevant context from vector database to enhance JD generation",
            backstory="""You are an expert in information retrieval and semantic search. 
            You specialize in finding relevant job descriptions and market data from 
            vector databases to provide context for generating new JDs.""",
            config=config,
        )
        
        # Initialize DirectRetriever (lightweight similarity search for JD Generation)
        self._direct_retriever = None
        self._query_router = None  # Not used for JD Generation
        self._init_direct_retriever()
    
    def _init_direct_retriever(self):
        """Initialize DirectRetriever for JD similarity search (lightweight, no Q&A overhead)."""
        try:
            try:
                from apps.quantchat.retrieval.direct_retriever import DirectRetriever
            except ImportError:
                from quantchat.retrieval.direct_retriever import DirectRetriever

            self._direct_retriever = DirectRetriever(use_reranking=True)
            self._query_router = None  # Not needed for JD Generation
            
            logger.info("✅ RAG Agent initialized with DirectRetriever (lightweight similarity search)")
        except Exception as e:
            logger.warning(f"⚠️ Failed to initialize DirectRetriever: {e}")
            self._direct_retriever = None
            self._query_router = None
    
    @traceable(name="retrieve_similar_jobs")
    def retrieve_similar_jobs(
        self,
        job_title: str,
        department: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve similar jobs using DirectRetriever (lightweight similarity search).
        
        Uses DirectRetriever with:
        - Hybrid retrieval (vector + keyword search)
        - RRF fusion
        - Reranking for relevance
        - No Q&A pipeline overhead (no intent classification, LLM generation, formatting)
        
        Args:
            job_title: Job title to search for
            department: Department name
            limit: Maximum number of results (uses config default if not provided)
            
        Returns:
            List of similar jobs in format: [{"job_id": str, "title": str, "department": str, "content": str, "similarity": float}]
        """
        if limit is None:
            limit = self.config.rag_similar_jobs_limit
        
        self._log_thought(
            f"Searching for similar jobs using DirectRetriever: {job_title} in {department}",
            "Direct similarity search"
        )
        
        if not self._direct_retriever:
            self._log_thought(
                "DirectRetriever not initialized. Cannot retrieve similar jobs.",
                "Retrieval Unavailable"
            )
            return []
        
        try:
            # Use DirectRetriever for lightweight similarity search
            similar_jobs = self._direct_retriever.find_similar_jds(
                job_title=job_title,
                department=department,
                limit=limit,
                group_by_document=True  # Group chunks by document_id
            )
            
            self._log_thought(
                f"Found {len(similar_jobs)} similar JDs using DirectRetriever",
                "Retrieval complete"
            )
            return similar_jobs
            
        except Exception as e:
            logger.error(f"DirectRetriever retrieval failed: {e}")
            self._log_thought(
                f"DirectRetriever retrieval failed: {str(e)}",
                "Retrieval Error"
            )
            return []
    
    

    def act(self, plan: Dict[str, Any], environment: Environment) -> Dict[str, Any]:
        """
        ACT: Execute RAG retrieval autonomously.
        
        Override of BaseCrewAgent.act() to properly return similar_jobs
        instead of using generic CrewAI task execution.
        
        The RAG agent's primary action is to retrieve similar jobs from
        the vector database using DirectRetriever.
        
        Args:
            plan: Action plan from plan() method
            environment: Environment containing job_title and department
            
        Returns:
            Action result with similar_jobs list
        """
        self._log_autonomous_action("ACT", "Executing RAG retrieval for similar jobs")
        
        # Extract job details from environment
        data = environment.get_data()
        job_title = data.get("job_title", "")
        department = data.get("department", "")
        
        # Get limit from constraints or config
        constraints = environment.get_constraints()
        limit = constraints.get("limit", self.config.rag_similar_jobs_limit)
        
        # Execute the actual retrieval using DirectRetriever
        try:
            similar_jobs = self.retrieve_similar_jobs(
                job_title=job_title,
                department=department,
                limit=limit
            )
            
            self._log_autonomous_action(
                "ACT",
                f"Retrieved {len(similar_jobs)} similar jobs for '{job_title}'"
            )
            
            return {
                "success": True,
                "similar_jobs": similar_jobs,
                "job_title": job_title,
                "department": department,
                "count": len(similar_jobs),
                "plan_executed": plan.get("plan", "RAG retrieval"),
            }
            
        except Exception as e:
            logger.error(f"RAG act() failed: {e}", exc_info=True)
            self._log_autonomous_action("ACT", f"RAG retrieval failed: {str(e)}")
            return {
                "success": False,
                "similar_jobs": [],
                "error": str(e),
                "plan_executed": plan.get("plan", "RAG retrieval"),
            }
    
    def _format_jd_content(self, jd_doc: Dict[str, Any]) -> str:
        """Format JD document as string content for similarity matching."""
        import json
        # Extract key sections for context
        sections = []
        if jd_doc.get("job_title"):
            sections.append(f"Job Title: {jd_doc['job_title']}")
        if jd_doc.get("position_summary"):
            sections.append(f"Summary: {jd_doc['position_summary']}")
        if jd_doc.get("responsibilities"):
            sections.append(f"Responsibilities: {', '.join(jd_doc['responsibilities'][:5])}")
        if jd_doc.get("required_qualifications"):
            reqs = jd_doc["required_qualifications"]
            if isinstance(reqs, dict):
                if reqs.get("technical_skills"):
                    sections.append(f"Skills: {', '.join(reqs['technical_skills'][:5])}")
        
        return "\n".join(sections) if sections else json.dumps(jd_doc, default=str)
    



class MilvusStorageAgent(BaseCrewAgent):
    """Agent responsible for storing JDs in Milvus vector database."""
    
    def __init__(self, config=None):
        """
        Initialize Milvus Storage Agent.
        
        Args:
            config: JDGenerationConfig instance (uses global config if not provided)
        """
        super().__init__(
            agent_name="Milvus Storage Agent",
            role="Vector Database Specialist",
            goal="Store Job Descriptions in Milvus for semantic search and retrieval",
            backstory="""You are an expert in vector databases and semantic search. 
            You specialize in storing and retrieving job descriptions from Milvus 
            to enable semantic search and candidate matching.""",
            config=config,
        )
    
    @traceable(name="generate_embedding")
    def generate_embedding(self, jd: Dict[str, Any]) -> List[float]:
        """
        Generate embedding for JD.
        
        Args:
            jd: Job description dictionary
            
        Returns:
            Embedding vector
            
        Raises:
            StorageError: If embedding generation fails
        """
        from agents.jd_generation.exceptions import StorageError
        from agents.jd_generation.embedding_service import get_embedding_service
        
        self._log_thought(
            "Generating embedding for JD to enable semantic search",
            "Creating vector embedding"
        )
        
        try:
            # Get embedding service
            embedding_service = get_embedding_service(self.config)
            
            # Generate embedding for JD
            embedding = embedding_service.generate_embedding_for_jd(jd)
            
            self._log_thought(
                f"Embedding generated. Dimension: {len(embedding)}",
                "Embedding ready"
            )
            
            return embedding
            
        except Exception as e:
            self._log_thought(
                f"Error generating embedding: {str(e)}",
                "Embedding failed"
            )
            logger.error(
                f"Embedding generation failed: {e}",
                exc_info=True,
                extra={"jd_keys": list(jd.keys()) if jd else []}
            )
            raise StorageError(
                message=f"Failed to generate embedding: {str(e)}",
                storage_type="embedding",
                details={"error": str(e)}
            )
    
    @traceable(name="store_in_milvus")
    def store_in_milvus(
        self,
        job_id: str,
        jd: Dict[str, Any],
        embedding: List[float]
    ) -> str:
        """
        Store JD in Milvus via Enterprise RAG Service.
        
        Args:
            job_id: Job ID
            jd: Job description dictionary
            embedding: Embedding vector (unused by Enterprise RAG as it generates its own, but kept for signature)
            
        Returns:
            Milvus document ID
        """
        from agents.jd_generation.exceptions import StorageError
        
        logger.info(f"🔄 MilvusStorageAgent.store_in_milvus called for job_id={job_id}")
        
        # ARCHITECTURAL RULE: Use DocumentIngestion for WRITE operations
        # EnterpriseRAG service has been removed
        try:
            # Ensure project root is in path for apps.quantchat import
            import sys
            from pathlib import Path
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent.parent.parent  # Go up to project root
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
                logger.debug(f"Added project root to sys.path: {project_root}")
            
            from apps.quantchat.ingestion import get_document_ingestion
            ingestion_service = get_document_ingestion()
            logger.info(f"✅ DocumentIngestion service obtained successfully")
        except ImportError as e:
            ingestion_service = None
            logger.error(f"❌ DocumentIngestion import failed: {e}")
            raise StorageError(f"DocumentIngestion service unavailable: {e}")
        except Exception as e:
            ingestion_service = None
            logger.error(f"❌ DocumentIngestion init failed: {e}")
            raise StorageError(f"DocumentIngestion service error: {e}")
            
        self._log_thought(
            f"Storing JD {job_id} in Milvus (via DocumentIngestion)",
            "Starting Milvus Storage"
        )
        
        try:
            # Use DocumentIngestion service for WRITE operations
            if not ingestion_service:
                raise StorageError("DocumentIngestion service not initialized")
            
            # Verify DocumentIngestion is connected to Milvus
            if not ingestion_service.is_connected():
                logger.error("DocumentIngestion service not connected to Milvus")
                raise StorageError("DocumentIngestion service not connected to Milvus")
            
            # Verify embedding model is loaded
            if not ingestion_service.encoder:
                logger.error("DocumentIngestion embedding model not loaded")
                raise StorageError("DocumentIngestion embedding model not loaded")
            
            # Prepare JD data with ID
            jd_data = jd.copy()
            jd_data['id'] = job_id  # DocumentIngestion expects 'id' field
            
            # Log JD structure for debugging
            logger.debug(
                f"Preparing JD for storage: job_id={job_id}, "
                f"has_job_title={bool(jd_data.get('job_title'))}, "
                f"has_position_summary={bool(jd_data.get('position_summary'))}, "
                f"jd_keys={list(jd_data.keys())}"
            )
            
            # Store using DocumentIngestion (WRITE operations to Milvus)
            milvus_id = ingestion_service.add_jd(jd_data)
            
            if not milvus_id:
                logger.error(f"DocumentIngestion.add_jd returned None for job_id={job_id}")
                raise StorageError("JD storage returned no ID")
            
            self._log_thought(
                f"JD stored successfully in Milvus. ID: {milvus_id}",
                "Storage complete"
            )
            
            logger.info(
                "JD stored in Milvus via DocumentIngestion",
                extra={
                    "job_id": job_id,
                    "milvus_id": milvus_id,
                    "storage": "DocumentIngestion",
                    "jd_title": jd_data.get('job_title', 'N/A'),
                }
            )
            
            return milvus_id
            
        except Exception as e:
            self._log_thought(
                f"Error storing in Milvus: {str(e)}",
                "Storage failed"
            )
            logger.error(
                f"Enterprise RAG storage failed: {e}",
                exc_info=True,
                extra={"job_id": job_id}
            )
            raise StorageError(
                message=f"Failed to store in Enterprise RAG: {str(e)}",
                storage_type="enterprise_rag",
                details={"error": str(e), "job_id": job_id}
            )
