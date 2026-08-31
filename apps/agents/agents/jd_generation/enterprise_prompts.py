"""
Enterprise JD Generation Prompts
================================
Prompt templates for generating 15-section Enterprise-Level Job Descriptions.
"""

ENTERPRISE_JD_GENERATION_PROMPT = """
You are an expert HR professional generating an ENTERPRISE-LEVEL Job Description with ALL 15 SECTIONS.

=== 🎯 USER INPUT (MUST MATCH EXACTLY) ===
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Field                  | User's Input              |
|------------------------|---------------------------|
| Job Title              | {job_title}               |
| Level                  | {job_level}               |
| Department             | {department}              |
| Location               | {location}                |
| Remote Work            | {remote_allowed}          |
| Additional Requirements| {user_requirements}       |
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

=== 🚨 CRITICAL: ADDITIONAL REQUIREMENTS MUST BE INCORPORATED 🚨 ===
The user has specified these ADDITIONAL REQUIREMENTS that MUST appear in the JD:
📋 "{user_requirements}"

⚠️ MANDATORY ACTIONS FOR ADDITIONAL REQUIREMENTS:
1. Each requirement MUST appear in the "responsibilities" section (as specific tasks)
2. Each requirement MUST appear in the "technical_skills" section (as skills)
3. Each requirement MUST appear in the "tools_technologies" section (as tools/technologies)
4. Reference them in the "position_summary"

🔥 EXAMPLE FOR INTEGRATION ROLES:
If user says "System Integration, Middleware, API Connectivity, Data Synchronization":
- position_summary: "...working with system integration, middleware platforms, API connectivity, and data synchronization..."
- responsibilities: 
  • "Design and implement system integration solutions to connect enterprise applications"
  • "Configure and maintain middleware platforms (e.g., MuleSoft, Boomi) for seamless connectivity"
  • "Develop and document APIs to enable secure and reliable API connectivity between systems"
  • "Implement data synchronization processes to ensure real-time data consistency across platforms"
- technical_skills: ["System Integration", "Middleware (MuleSoft, Boomi)", "API Development (REST, SOAP)", "Data Synchronization"]
- tools_technologies: ["MuleSoft", "Boomi", "REST APIs", "SOAP", "Kafka", "RabbitMQ", "SQL", "Git"]

🔥 EXAMPLE FOR DATA ROLES:
If user says "SQL & Excel, Client Communication":
- responsibilities: "Perform data analysis using SQL and Excel", "Communicate with clients..."
- technical_skills: ["SQL", "Microsoft Excel (Advanced)", "Client Communication"]
- tools_technologies: ["SQL Server", "Microsoft Excel", "Communication Tools"]

⚠️ DO NOT IGNORE USER REQUIREMENTS - THEY MUST BE PROMINENTLY FEATURED!

=== 🚨🚨🚨 CRITICAL: JOB LEVEL IS "{job_level}" 🚨🚨🚨 ===
THE ENTIRE JD MUST BE TAILORED TO A "{job_level}" LEVEL POSITION.
This is NOT optional - EVERY section must reflect "{job_level}" level expectations.

=== LEVEL-SPECIFIC REQUIREMENTS FOR "{job_level}" ===
Based on the job level "{job_level}", you MUST apply these guidelines for ALL SECTIONS (Summary, Responsibilities, Education, Skills, Reporting):

╔═══════════════════════════════════════════════════════════════════════════════╗
║ IF JOB_LEVEL = "JUNIOR" OR "ENTRY":                                           ║
║ • Experience: EXACTLY "0-2 years" (NOT 3+, NOT "2-4", NOT "0-3")             ║
║ • Position Summary: "We are seeking an enthusiastic...", "Join our team to learn...", "Work under guidance..." 
║ • Action verbs: "Assist with", "Support", "Learn", "Execute", "Participate in" (NEVER "Lead", "Manage", "Drive") 
║ • Reports to: Team Lead or Senior Engineer                                    ║
║ • Responsibilities: Task execution, learning, supporting senior team members (NO strategic/mentoring tasks) 
║ • Autonomy: Works under close supervision with guidance                      ║
║ • Education: Bachelor's degree, recent graduates welcome                     ║
║ • KPIs: Task completion rate, learning speed, bug-free delivery              ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ IF JOB_LEVEL = "MID" OR "INTERMEDIATE":                                       ║
║ • Experience: EXACTLY "3-5 years" (NOT 0-2, NOT 5-8, NOT "2-5")              ║
║ • Position Summary: "We are looking for a skilled...", "Take ownership of...", "Collaborate with..." 
║ • Action verbs: "Develop", "Implement", "Collaborate", "Analyze", "Manage"   ║
║ • Reports to: Engineering Manager or Team Lead                                ║
║ • Responsibilities: Independent execution, feature ownership, collaboration  ║
║ • Autonomy: Works independently with periodic check-ins                      ║
║ • Education: Bachelor's degree required                                       ║
║ • KPIs: Feature delivery, code quality, peer review participation            ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ IF JOB_LEVEL = "SENIOR":                                                      ║
║ • Experience: EXACTLY "5-8 years" (NOT 3-5, NOT 8+)                          ║
║ • Position Summary: "We need an experienced leader...", "Drive technical direction...", "Mentor junior engineers..." 
║ • Action verbs: "Lead", "Design", "Architect", "Mentor", "Drive", "Define"   ║
║ • Reports to: Director of Engineering or VP                                   ║
║ • Responsibilities: Technical leadership, system design, mentoring, complex problem solving 
║ • Autonomy: Fully autonomous, drives initiatives                             ║
║ • Education: Bachelor's minimum, Master's preferred                          ║
║ • KPIs: System architecture scalability, team velocity impact, mentoring outcomes 
╠═══════════════════════════════════════════════════════════════════════════════╣
║ IF JOB_LEVEL = "LEAD" OR "PRINCIPAL":                                         ║
║ • Experience: EXACTLY "8+ years"                                             ║
║ • Position Summary: "We require a visionary leader...", "Transform our capabilities...", "Set strategic direction..." 
║ • Action verbs: "Define", "Transform", "Influence", "Pioneer", "Establish"   ║
║ • Reports to: VP of Engineering or CTO                                        ║
║ • Responsibilities: Strategic vision, technical roadmap, cross-team impact   ║
║ • Autonomy: Sets direction for entire organization                           ║
║ • Education: Master's preferred, advanced certifications                      ║
║ • KPIs: Organization-wide impact, technical innovation, long-term stability  ║
╚═══════════════════════════════════════════════════════════════════════════════╝

⚠️⚠️⚠️ MOST IMPORTANT RULE: The generated content MUST match "{job_level}" level. 
If "{job_level}" is Junior, DO NOT include "Lead a team" or "5+ years experience".
If "{job_level}" is Junior, use verbs like "Assist", "Support", "Learn".
If "{job_level}" is Senior, DO NOT include "Work under supervision".

=== ⚠️ CRITICAL INSTRUCTIONS - READ CAREFULLY ===
1. DO NOT use placeholder text like "[Insert here]", "[Company Name]", "[URL]"
2. ⚠️ CRITICAL: Generate content SPECIFICALLY for "{job_title}" - NOT for a different role
3. ⚠️ CRITICAL: INCORPORATE ALL Additional Requirements: "{user_requirements}"
4. ⚠️ CRITICAL: Match the experience/complexity to "{job_level}" level
5. Include ACTUAL technical skills that are DIRECTLY relevant to "{job_title}"
6. Be SPECIFIC - mention actual technologies, tools, and methodologies used by a "{job_title}"
7. Start all responsibilities with action verbs appropriate for {job_level}
8. Include numeric years in experience requirements (based on {job_level})
9. MANDATORY: Use EXACTLY the Malomatia company information provided below
10. ⚠️ CRITICAL: DO NOT CHANGE THE JOB TITLE - Use EXACTLY "{job_title}" as provided

=== 🧠 THINK FIRST - UNDERSTAND THE ROLE ===
Before generating ANY content, you MUST think about what a "{job_title}" actually does:

1. What is the PRIMARY focus of a "{job_title}"?
2. What technologies/tools does a "{job_title}" use DAILY?
3. What are the CORE responsibilities of a "{job_title}"?
4. What skills are ESSENTIAL for a "{job_title}"?
5. Who does a "{job_title}" collaborate with?

⚠️ CRITICAL: DO NOT generate generic "software engineer" or "developer" content.
⚠️ CRITICAL: Generate content SPECIFIC to "{job_title}" - every skill, tool, and responsibility must be relevant.
⚠️ CRITICAL: If "{job_title}" is a specialized role (Frontend, Backend, Data, DevOps, etc.), use ONLY skills/tools for that specialization.

=== 🚫 COMMON MISTAKES TO AVOID ===
- DO NOT list Java, Python, C++, Spring for a Frontend Developer role
- DO NOT list React, Vue, CSS for a Backend Developer role
- DO NOT list web frameworks for a Data Scientist role
- DO NOT list application development for a DevOps role
- DO NOT use generic responsibilities that could apply to any developer

=== RELEVANCE VALIDATION ===
For EVERY item you generate, ask:
- "Would a {job_title} actually do this / use this / need this?"
- If the answer is NO, do not include it.
- If the answer is MAYBE, think harder about what a {job_title} specifically does.

User's additional requirements to incorporate: {user_requirements}

=== GENERATE ALL 15 SECTIONS ===

**SECTION 1 - JOB TITLE:**
⚠️ MANDATORY - USE EXACTLY: "{job_title}"
DO NOT change, modify, or substitute the job title. The user specifically requested this exact title.

**SECTION 2 - DEPARTMENT / TEAM:**
Format: {department} - [Relevant Team Name]
Use ONLY plain text. DO NOT use special characters like arrows or unicode symbols.
Example: AI & Advanced Engineering - Autonomous Systems Team

**SECTION 3 - LOCATION & WORK MODEL:**
City: {location}
Country: Qatar
Work Model: {work_model}
Travel Required: No (or minimal <10%)

**SECTION 4 - ABOUT THE COMPANY:**
⚠️ MANDATORY - USE THIS EXACT TEXT (DO NOT MODIFY OR REPLACE):
"Malomatia is a leading provider of Information Technology services and solutions headquartered in Doha, Qatar, delivering digital transformation, managed services, and operational excellence across multiple sectors and delivery locations. Founded in 2008 at Manarat Lusail Tower, Malomatia supports Qatar's National Vision 2030 while enabling clients through reliable technology services, process improvement, and knowledge-based innovation."
⚠️ DO NOT use "Acme Corp" or any other company name - the company is MALOMATIA

**SECTION 5 - POSITION SUMMARY:**
Write 3-5 sentences SPECIFICALLY for a "{job_level} {job_title}" covering:
- What this {job_level} {job_title} role exists for (be specific to this title AND level)
- Key business impact a {job_level} {job_title} makes
- Who a {job_level} {job_title} collaborates with
- Why this role matters at Malomatia
- ⚠️ MUST mention the user's additional requirements: "{user_requirements}"

⚠️ CRITICAL: The summary MUST mention "{job_title}" by name and describe what a {job_level}-level professional does.

⚠️ LEVEL-SPECIFIC SUMMARY TEMPLATES:
╔═══════════════════════════════════════════════════════════════════════════════╗
║ JUNIOR SUMMARY MUST INCLUDE:                                                  ║
║ - "under the guidance of senior engineers"                                   ║
║ - "support the design/implementation"                                        ║
║ - "develop foundational skills"                                              ║
║ - "learn and grow"                                                           ║
║ Example: "The Junior {job_title} will support the design and implementation  ║
║ of [solutions] under the guidance of senior engineers. This role focuses on  ║
║ developing foundational skills in [technologies] while contributing to       ║
║ Malomatia's digital transformation initiatives."                             ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ MID-LEVEL SUMMARY MUST INCLUDE:                                               ║
║ - "independently develop and implement"                                      ║
║ - "collaborate with cross-functional teams"                                  ║
║ - "take ownership of"                                                        ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║ SENIOR SUMMARY MUST INCLUDE:                                                  ║
║ - "lead the design and architecture"                                         ║
║ - "mentor junior team members"                                               ║
║ - "drive strategic initiatives"                                              ║
║ - "technical leadership"                                                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

**SECTION 6 - KEY RESPONSIBILITIES:**
⚠️🚨 MANDATORY: Generate EXACTLY 10-12 bullet points. MINIMUM 10, MAXIMUM 12.
❌ REJECTION CRITERIA: If you generate fewer than 10 responsibilities, the JD is INVALID.
✅ VALIDATION: Count your responsibilities before output. Must be 10, 11, or 12.

⚠️ LEVEL-APPROPRIATE ACTION VERBS FOR "{job_level}":
╔═══════════════════════════════════════════════════════════════════════════════╗
║ Junior: "Assist with", "Support", "Learn", "Execute", "Participate in", "Help"║
║ Mid: "Develop", "Implement", "Analyze", "Collaborate", "Manage", "Execute"   ║
║ Senior: "Lead", "Design", "Architect", "Mentor", "Drive", "Establish"        ║
║ Lead: "Transform", "Influence", "Shape", "Spearhead", "Pioneer"              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

🚫🚫🚫 DO NOT GENERATE REPETITIVE OR HOLLOW RESPONSIBILITIES 🚫🚫🚫
❌ WRONG (Repetitive pattern - NEVER USE):
- "Apply System Integration expertise to deliver project objectives"
- "Apply Python expertise to deliver high-quality solutions"
- "Apply Machine Learning expertise to deliver high-quality solutions"
- "Utilize X skills to..."
- "Leverage X expertise..."
- "Demonstrate proficiency in..."

These are CAPABILITIES, not TASKS. They tell the candidate nothing about what they will actually DO.

✅ CORRECT (Specific, actionable, outcome-focused):
- "Design and implement integration solutions using middleware, APIs, and data synchronization techniques to ensure seamless cross-platform connectivity"
- "Clean, preprocess, and validate datasets to ensure data quality and integrity for analysis"
- "Build and evaluate baseline machine learning models (regression, classification) under senior guidance"
- "Write and optimize SQL queries to extract and transform data from relational databases"

⚠️ RESPONSIBILITY QUALITY RULES:
1. Each responsibility must be UNIQUE - no repetitive patterns
2. Combine related skills into ONE impactful responsibility
3. Focus on OUTCOMES and IMPACT, not just "applying expertise"
4. Be SPECIFIC about what the person will actually DO day-to-day
5. Include HOW and WHY, not just WHAT
6. NEVER start with "Apply", "Utilize", "Leverage", or "Demonstrate" followed by a skill name
7. Responsibilities must describe REAL TASKS that can be measured

⚠️🚨 MANDATORY: At least 3 responsibilities MUST incorporate user's requirements:
User's requirements: "{user_requirements}"

Level-appropriate responsibility breakdown for {job_level} {job_title}:
- Junior: 6 execution/support tasks, 2 learning tasks, 2 collaboration tasks
- Mid: 5 independent tasks, 3 collaboration, 2 process improvement  
- Senior: 4 leadership/strategy, 3 mentoring/review, 3 execution

**SECTION 7 - REQUIRED QUALIFICATIONS:**
Include THREE subsections SPECIFIC to "{job_level} {job_title}":

📚 Education: Degree relevant to {job_title} field
- Junior: Bachelor's degree. Recent graduates welcome.
- Mid: Bachelor's degree required.
- Senior: Bachelor's required, Master's preferred.
- Lead: Master's preferred, advanced certifications.

⚠️⚠️⚠️ EXPERIENCE - CRITICAL - MUST MATCH "{job_level}":
╔═══════════════════════════════════════════════════════════════════════════════╗
║ Junior/Entry: "0-2 years of relevant experience. Internships count."         ║
║ Mid-level:    "3-5 years in {job_title} or related field."                   ║
║ Senior:       "5-8+ years with demonstrated expertise in the field."         ║
║ Lead/Principal: "8-12+ years with leadership and strategic experience."      ║
╚═══════════════════════════════════════════════════════════════════════════════╝
⚠️ USE THE EXPERIENCE FOR "{job_level}" ONLY!
❌ DO NOT generate "5+ years" for a Junior role
❌ DO NOT generate "0-2 years" for a Senior role

🔧 Technical Skills (8-12 items):
⚠️🚨 MANDATORY: Include ALL skills from user's requirements: "{user_requirements}"
These MUST appear in technical_skills: {user_requirements}

**SECTION 8 - PREFERRED QUALIFICATIONS:**
List 4-6 nice-to-have items RELEVANT to "{job_level} {job_title}":
- Certifications relevant to {job_title} at {job_level} level
- Additional experience areas for {job_title}
- Bonus skills that enhance a {job_title}'s effectiveness
- For Senior+: Leadership or mentoring experience

**SECTION 9 - CORE COMPETENCIES / SOFT SKILLS:**
List 5-7 soft skills important for a "{job_level} {job_title}":

Level-appropriate soft skills:
- Junior: Willingness to learn, attention to detail, team collaboration, communication
- Mid: Problem-solving, time management, stakeholder communication, initiative
- Senior: Leadership, strategic thinking, mentoring, influence, decision-making

⚠️ If user mentioned soft skills in "{user_requirements}", include them here

**SECTION 10 - TOOLS & TECHNOLOGIES USED:**
List 10-15 tools that a "{job_title}" would ACTUALLY use:
⚠️🚨 MANDATORY: Include tools related to user's requirements: "{user_requirements}"

⚠️ LEVEL-APPROPRIATE TOOL EXPECTATIONS FOR "{job_level}":
╔═══════════════════════════════════════════════════════════════════════════════╗
║ Junior/Entry: List CORE tools as required, ADVANCED tools as "Exposure to"   ║
║   Example: "Git, REST APIs, Postman, SQL (Exposure to: Kubernetes, Kafka)"   ║
║                                                                               ║
║ Mid-Level: List most tools as required, some advanced as "preferred"         ║
║   Example: "Docker, APIs, SQL, Cloud basics (Preferred: Kubernetes)"         ║
║                                                                               ║
║ Senior/Lead: List all tools as required, expect mastery                      ║
║   Example: "Kubernetes, Kafka, Terraform, AWS, Docker, CI/CD pipelines"      ║
╚═══════════════════════════════════════════════════════════════════════════════╝

For "Frontend Developer": HTML, CSS, JavaScript, TypeScript, React, Vue, Angular, Webpack, npm, Figma, Chrome DevTools, Jest, Cypress
For "Backend Developer": Python, Java, Node.js, PostgreSQL, MongoDB, Redis, Docker, REST APIs, GraphQL
For "Data Scientist": Python, R, TensorFlow, PyTorch, Pandas, NumPy, Jupyter, SQL, Tableau
For "DevOps Engineer": Docker, Kubernetes, Terraform, AWS, Jenkins, GitHub Actions, Prometheus, Grafana
For "Systems Integration Engineer": REST APIs, SOAP, ESB (MuleSoft, Boomi), SQL, Git, Postman (Junior: Exposure to Kafka, Kubernetes)

⚠️ Choose tools appropriate for "{job_title}" AND "{job_level}"!

**SECTION 11 - SUCCESS METRICS / KPIs:**
⚠️ MANDATORY: You MUST generate 4-6 measurable success criteria SPECIFIC to "{job_title}".
This section is REQUIRED and cannot be empty.

For a "{job_title}", generate metrics such as:
- Performance indicators that a {job_title} would be measured on
- Quality metrics specific to {job_title} deliverables and outcomes
- Efficiency metrics relevant to {job_title} work (e.g., time to completion, accuracy rates)
- Impact metrics showing the business value a {job_title} provides
- Compliance and governance metrics (if applicable to {job_title})
- Collaboration and stakeholder satisfaction metrics for {job_title}

Examples by role type:
- For Governance/Compliance roles: Compliance audit scores, policy adherence rates, risk reduction metrics, audit findings resolution time
- For Engineering roles: Code quality metrics, deployment success rates, system uptime, bug reduction
- For Management roles: Team performance, project delivery timelines, stakeholder satisfaction, budget adherence
- For Security roles: Incident response time, vulnerability remediation rates, security posture improvements

⚠️ CRITICAL: Make each metric MEASURABLE and SPECIFIC to "{job_title}". Avoid generic metrics that could apply to any role.

**SECTION 12 - WORK ENVIRONMENT / REPORTING STRUCTURE:**
Include structure appropriate for a "{job_level} {job_title}":

⚠️ REPORTS TO - MUST MATCH "{job_level}":
╔═══════════════════════════════════════════════════════════════════════════════╗
║ Junior/Entry: Reports to Team Lead or Senior Engineer                        ║
║ Mid-level:    Reports to Engineering Manager or Team Lead                    ║
║ Senior:       Reports to Director of Engineering or VP                       ║
║ Lead/Principal: Reports to VP of Engineering or CTO                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

- Team size: 5-10 (varies by department)
- Collaborates with: Teams a {job_title} would work with
- Collaboration Mode: Agile / cross-functional squads

**SECTION 13 - COMPENSATION & BENEFITS:**
List 6-8 benefits:
- Competitive salary + performance bonus
- Health, dental, and vision insurance
- Paid time off + remote work flexibility
- Professional development budget
- 401(k) matching

**SECTION 14 - EQUAL OPPORTUNITY STATEMENT:**
⚠️ MANDATORY - USE THIS EXACT TEXT (DO NOT MODIFY):
"Malomatia is an Equal Opportunity Employer. We celebrate diversity and are committed to creating an inclusive environment for all employees regardless of race, religion, gender, age, nationality, disability, or any other protected status. We welcome applications from all qualified candidates."

**SECTION 15 - APPLICATION INSTRUCTIONS:**
⚠️ MANDATORY - USE THESE EXACT VALUES:
- Apply at: https://careers.malomatia.com/apply
- Email: careers@malomatia.com
- Required materials: Resume, Cover Letter, Portfolio/GitHub (if applicable)

=== OUTPUT FORMAT ===
Return a valid JSON object with this EXACT structure:
⚠️ IMPORTANT: The job_title MUST be exactly "{job_title}" - do not change it!
{{
    "job_title": "{job_title}",
    "department": "{department}",
    "team": "Relevant Team Name",
    "location": {{
        "city": "{location}",
        "country": "Qatar",
        "work_model": "{work_model}",
        "travel_required": false,
        "travel_percentage": null
    }},
    "about_company": "Malomatia is a leading provider of Information Technology services and solutions headquartered in Doha, Qatar, delivering digital transformation, managed services, and operational excellence across multiple sectors and delivery locations. Founded in 2008 at Manarat Lusail Tower, Malomatia supports Qatar's National Vision 2030 while enabling clients through reliable technology services, process improvement, and knowledge-based innovation.",
    "position_summary": "3-5 sentence role summary",
    "responsibilities": [
        "Action verb responsibility 1 - specific to {job_title}",
        "Action verb responsibility 2 - specific to {job_title}",
        "Action verb responsibility 3 - specific to {job_title}",
        "Action verb responsibility 4 - specific to {job_title}",
        "Action verb responsibility 5 - specific to {job_title}",
        "Action verb responsibility 6 - specific to {job_title}",
        "Action verb responsibility 7 - specific to {job_title}",
        "Action verb responsibility 8 - specific to {job_title}",
        "Action verb responsibility 9 - specific to {job_title}",
        "Action verb responsibility 10 - specific to {job_title}"
    ],
    "required_qualifications": {{
        "education": "Degree requirement",
        "experience": "X+ years of specific experience",
        "technical_skills": ["Skill1", "Skill2", "Skill3", "Skill4", "Skill5", "Skill6", "Skill7", "Skill8"]
    }},
    "preferred_qualifications": ["Preferred item 1", "Preferred item 2", "Preferred item 3", "Preferred item 4"],
    "soft_skills": ["Soft skill 1", "Soft skill 2", "Soft skill 3", "Soft skill 4", "Soft skill 5"],
    "tools_technologies": ["Tool1", "Tool2", "Tool3", "Tool4", "Tool5", "Tool6", "Tool7", "Tool8", "Tool9", "Tool10"],
    "success_metrics": ["Metric 1", "Metric 2", "Metric 3", "Metric 4"],
    "work_environment": {{
        "reports_to": "Manager Title",
        "team_size": 8,
        "collaborates_with": ["Team1", "Team2"],
        "collaboration_mode": "Agile"
    }},
    "compensation_benefits": ["Benefit 1", "Benefit 2", "Benefit 3", "Benefit 4"],
    "equal_opportunity_statement": "Malomatia is an Equal Opportunity Employer...",
    "application_instructions": {{
        "apply_url": "https://careers.malomatia.com/apply",
        "email": "careers@malomatia.com",
        "required_materials": ["Resume", "Cover Letter"]
    }}
}}

⚠️ FINAL CHECKLIST BEFORE GENERATING:
1. Is the job_title EXACTLY "{job_title}"? (DO NOT CHANGE IT)
2. Are ALL responsibilities relevant to what a "{job_title}" does?
3. Are ALL technical skills relevant to "{job_title}"?
4. Have I incorporated the user's requirements: "{user_requirements}"?
5. Is the content specific to "{job_title}" and NOT generic?

🔢 MANDATORY COUNT VALIDATION (REJECT IF NOT MET):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Section                | MINIMUM | MAXIMUM |
|------------------------|---------|---------|
| responsibilities       |   10    |   12    |
| technical_skills       |    8    |   12    |
| preferred_qualifications|   4    |    6    |
| soft_skills            |    5    |    7    |
| tools_technologies     |   10    |   15    |
| success_metrics        |    4    |    6    |
| compensation_benefits  |    4    |    6    |
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ COUNT YOUR ITEMS BEFORE OUTPUT. If any section is below minimum, ADD MORE ITEMS.

⚠️🚨 CRITICAL OUTPUT RULES - READ CAREFULLY 🚨⚠️
- OUTPUT ONLY THE JSON OBJECT - nothing else
- DO NOT include your reasoning, thinking, or planning in the output
- DO NOT include phrases like "I will now execute", "Step 1:", "Calling tool:", etc.
- DO NOT include markdown like **ACT**, **OBSERVE**, **THINK**, **PLAN**, **REFLECT**
- DO NOT include tool call information or parameters
- DO NOT include code blocks with ```json``` except for the final output
- The position_summary MUST be actual job content, NOT your thought process
- Every field MUST contain FINAL CONTENT, not your reasoning about what to generate

❌ WRONG OUTPUT EXAMPLE (DO NOT DO THIS):
{{
    "position_summary": "**ACT**: I will now execute the plan. Step 1: Retrieve similar jobs..."
}}

✅ CORRECT OUTPUT EXAMPLE:
{{
    "position_summary": "The Senior Cybersecurity Analyst is responsible for protecting organizational assets..."
}}

=== 🚨 FINAL LEVEL VALIDATION - "{job_level}" 🚨 ===
BEFORE generating output, verify YOUR JD matches "{job_level}" level:

╔═════════════════════════════════════════════════════════════════════════════════╗
║ CHECKLIST FOR "{job_level}" LEVEL - ALL MUST BE TRUE:                          ║
╠═════════════════════════════════════════════════════════════════════════════════╣
║ ✓ Experience years match {job_level} (Junior=0-2, Mid=3-5, Senior=5-8+)        ║
║ ✓ Action verbs in responsibilities match {job_level}                           ║
║ ✓ Reports_to title matches {job_level}                                         ║
║ ✓ Position summary describes a {job_level}-level professional                  ║
║ ✓ KPIs/Success metrics are appropriate for {job_level}                         ║
║ ✓ Education requirements match {job_level}                                     ║
╚═════════════════════════════════════════════════════════════════════════════════╝

❌ REJECTION EXAMPLES:
- Junior with "5+ years experience" = WRONG → Use "0-2 years"
- Junior with "Lead the team" = WRONG → Use "Assist the team"
- Senior with "1-3 years experience" = WRONG → Use "5-8+ years"
- Senior reporting to "Team Lead" = WRONG → Report to "Director"

Generate the COMPLETE enterprise JD now for: {job_level} {job_title} in {department}
Make sure EVERY section is SPECIFICALLY relevant to a "{job_title}" role.
OUTPUT ONLY THE JSON OBJECT:
"""

ENTERPRISE_JD_EXTRACTION_PROMPT = """You are a JSON extraction expert. Extract the 15-section Enterprise Job Description from this text and return ONLY valid JSON.

=== JOB DESCRIPTION TEXT ===
{text}

=== CRITICAL INSTRUCTIONS ===
1. Extract ALL content from the text above into the enterprise format
2. DO NOT use placeholder text - use the ACTUAL content from the JD
3. If a section is missing, provide sensible defaults
4. Return ONLY the JSON object, no markdown, no explanation

⚠️ IMPORTANT: CLEAN UP CONTAMINATED CONTENT ⚠️
If you see ANY of the following in the text, REMOVE IT and replace with proper content:
- "**ACT**:", "**OBSERVE**:", "**THINK**:", "**PLAN**:", "**REFLECT**:"
- "I will now execute", "Step 1:", "Calling tool:", "Parameters:"
- Tool names like "retrieve_similar_jobs", "search_milvus"
- JSON code blocks showing tool outputs

These are agent reasoning artifacts that accidentally leaked into the content.
Replace them with appropriate job description content based on context.

=== REQUIRED JSON STRUCTURE ===
{{
    "job_title": "The exact job title",
    "department": "Department name",
    "team": "Team name or null",
    "location": {{
        "city": "Location to be confirmed",
        "country": "",
        "work_model": "On-site|Hybrid|Remote",
        "travel_required": false,
        "travel_percentage": null
    }},
    "about_company": "Malomatia is a leading provider of Information Technology services and solutions in Qatar...",
    "position_summary": "Position summary (3-5 sentences)",
    "responsibilities": ["Responsibility 1", "Responsibility 2"],
    "required_qualifications": {{
        "education": "Education requirement",
        "experience": "Experience requirement with years",
        "technical_skills": ["Skill1", "Skill2"]
    }},
    "preferred_qualifications": ["Preferred 1", "Preferred 2"],
    "soft_skills": ["Soft skill 1", "Soft skill 2"],
    "tools_technologies": ["Tool1", "Tool2"],
    "success_metrics": ["Metric 1", "Metric 2"],
    "work_environment": {{
        "reports_to": "Manager title",
        "team_size": 8,
        "collaborates_with": ["Team1", "Team2"],
        "collaboration_mode": "Agile"
    }},
    "compensation_benefits": ["Benefit 1", "Benefit 2"],
    "equal_opportunity_statement": "Malomatia is an Equal Opportunity Employer...",
    "application_instructions": {{
        "apply_url": "URL or null",
        "email": "Email or null",
        "required_materials": ["Resume", "Cover Letter"]
    }}
}}

Return the JSON now:"""

ENTERPRISE_JD_REFINEMENT_PROMPT = """You are an expert HR content editor. Refine this Enterprise Job Description to ensure it meets professional standards.

=== 🎯 JOB LEVEL: {job_level} ===
This is a {job_level} position. ALL content MUST be appropriate for this level.

=== CURRENT JD ===
{current_jd}

=== 🚨 LEVEL-SPECIFIC ACTION VERBS (MANDATORY) ===
Based on the job level "{job_level}", responsibilities MUST use these action verbs:

╔═══════════════════════════════════════════════════════════════════════════════╗
║ JUNIOR/ENTRY LEVEL: "Assist with", "Support", "Learn", "Execute", "Participate" ║
║ MID-LEVEL:          "Develop", "Implement", "Collaborate", "Analyze", "Manage"  ║
║ SENIOR LEVEL:       "Lead", "Design", "Architect", "Mentor", "Drive", "Define"  ║
║ LEAD/PRINCIPAL:     "Define", "Transform", "Influence", "Pioneer", "Establish"  ║
╚═══════════════════════════════════════════════════════════════════════════════╝

=== CRITICAL CONSTRAINTS - DO NOT CHANGE THESE ===
⚠️ DO NOT modify the job_title - keep it EXACTLY as provided
⚠️ DO NOT modify the job_level field - keep it EXACTLY as "{job_level}"
⚠️ EXPERIENCE MUST match job_level:
   • Junior/Entry Level → 0-2 years (NOT 3+)
   • Mid-Level → 3-5 years (NOT 0-2, NOT 6+)
   • Senior Level → 5-8 years (NOT under 5)
   • Lead/Principal → 8+ years (NOT under 8)
⚠️ DO NOT modify the about_company section - it must remain Malomatia's description
⚠️ DO NOT modify the equal_opportunity_statement - it must remain Malomatia's statement
⚠️ DO NOT modify the application_instructions URLs - they must remain malomatia.com

=== 🔢 MANDATORY COUNT VALIDATION (FIX IF BELOW MINIMUM) ===
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Section                | MINIMUM | MAXIMUM |
|------------------------|---------|---------|
| responsibilities       |   10    |   12    |
| technical_skills       |    8    |   12    |
| preferred_qualifications|   4    |    6    |
| soft_skills            |    5    |    7    |
| tools_technologies     |   10    |   15    |
| success_metrics        |    4    |    6    |
| compensation_benefits  |    4    |    6    |
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ COUNT EACH SECTION. If ANY section is BELOW minimum, ADD relevant items until minimum is met.
⚠️ This is a HARD REQUIREMENT - the JD MUST meet these minimums.

=== REFINEMENT GOALS ===
1. Enhance clarity and readability
2. Ensure consistency in tone and style
3. Improve professional language
4. ⚠️ Ensure ALL sections meet the minimum item counts above
5. Remove redundancy (but keep minimum counts)
6. Make it more engaging while maintaining professionalism
7. Ensure responsibilities start with action verbs
8. Verify experience requirements include numeric years
9. Check that technical skills are ATS-friendly
10. ⚠️ PRESERVE the exact job_title - do not change or "improve" it

=== CONTEXT ===
Similar jobs found: {similar_jobs_count}
User requirements: {user_requirements}

Return the refined JD as a valid JSON object with the same 15-section structure.
⚠️ REMINDER: The job_title must remain EXACTLY as provided in the current JD.
⚠️ REMINDER: ALL sections must meet the MINIMUM item counts.
"""


def get_enterprise_generation_prompt(
    job_title: str,
    job_level: str,
    department: str,
    location: str,
    remote_allowed: bool,
    user_requirements: str = ""
) -> str:
    """Get the enterprise JD generation prompt with filled values."""
    
    # Generate role-specific guidance based on job title
    role_guidance = _get_role_specific_guidance(job_title)
    
    prompt = ENTERPRISE_JD_GENERATION_PROMPT.format(
        job_title=job_title,
        job_level=job_level,
        department=department,
        location=location if location else "Location to be confirmed",
        remote_allowed="Yes" if remote_allowed else "No",
        work_model="Remote" if remote_allowed else "Hybrid",
        user_requirements=user_requirements if user_requirements else "None specified"
    )
    
    # Insert role-specific guidance before the output format section
    if role_guidance:
        prompt = prompt.replace(
            "=== OUTPUT FORMAT ===",
            f"{role_guidance}\n\n=== OUTPUT FORMAT ==="
        )
    
    return prompt


def _get_role_specific_guidance(job_title: str) -> str:
    """
    Generate comprehensive role-specific guidance to ensure 10/10 quality JDs.
    This ensures the JD content is highly relevant to the actual job title.
    """
    title_lower = job_title.lower()
    
    # ===== TECHNOLOGY / ENGINEERING ROLES =====
    if any(kw in title_lower for kw in ["frontend", "front-end", "front end", "ui developer", "react", "angular", "vue"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR FRONTEND DEVELOPER ===
🎯 PRIMARY FOCUS: Building user interfaces, responsive design, browser compatibility
📦 CORE TECHNOLOGIES: HTML5, CSS3, JavaScript/TypeScript, React/Vue/Angular, Webpack, npm/yarn
🔧 TOOLS: Figma, Chrome DevTools, Jest, Cypress, Storybook, ESLint, Prettier
📊 METRICS: Page load time, Core Web Vitals, accessibility scores, cross-browser compatibility
👥 COLLABORATES WITH: UX Designers, Backend Developers, Product Managers
❌ DO NOT INCLUDE: Backend frameworks (Spring, Django), databases, DevOps tools"""

    elif any(kw in title_lower for kw in ["backend", "back-end", "back end", "server", "api developer"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR BACKEND DEVELOPER ===
🎯 PRIMARY FOCUS: Server-side logic, APIs, database design, system architecture
📦 CORE TECHNOLOGIES: Python/Java/Node.js/Go, PostgreSQL/MySQL, MongoDB, Redis, REST/GraphQL
🔧 TOOLS: Docker, Postman, Git, CI/CD pipelines, AWS/GCP/Azure, Swagger
📊 METRICS: API response time, uptime, error rates, database query performance
👥 COLLABORATES WITH: Frontend Developers, DevOps, Database Administrators
❌ DO NOT INCLUDE: Frontend frameworks (React, Vue), CSS, UI/UX design tools"""

    elif any(kw in title_lower for kw in ["fullstack", "full-stack", "full stack"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR FULLSTACK DEVELOPER ===
🎯 PRIMARY FOCUS: End-to-end application development, both frontend and backend
📦 CORE TECHNOLOGIES: JavaScript/TypeScript, React/Vue + Node.js, PostgreSQL, MongoDB
🔧 TOOLS: VS Code, Git, Docker, AWS/Vercel, Postman, Jest, Cypress
📊 METRICS: Feature delivery velocity, code quality, system performance, user satisfaction
👥 COLLABORATES WITH: Product Managers, UX Designers, DevOps Engineers
✅ INCLUDE: Both frontend AND backend technologies in balanced proportion"""

    elif any(kw in title_lower for kw in ["devops", "sre", "site reliability", "platform engineer", "infrastructure"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR DEVOPS/SRE ===
🎯 PRIMARY FOCUS: CI/CD pipelines, infrastructure automation, system reliability
📦 CORE TECHNOLOGIES: Docker, Kubernetes, Terraform, Ansible, AWS/GCP/Azure
🔧 TOOLS: Jenkins/GitHub Actions, Prometheus, Grafana, ELK Stack, Datadog
📊 METRICS: Deployment frequency, MTTR, change failure rate, system uptime (99.9%+)
👥 COLLABORATES WITH: Development Teams, Security, Operations
❌ DO NOT INCLUDE: Application development frameworks, UI/UX tools"""

    elif any(kw in title_lower for kw in ["data scientist", "machine learning", "ml engineer", "ai engineer"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR DATA SCIENTIST / ML ENGINEER ===
🎯 PRIMARY FOCUS: Building ML models, statistical analysis, data-driven insights
📦 CORE TECHNOLOGIES: Python, TensorFlow/PyTorch, Scikit-learn, Pandas, NumPy, SQL
🔧 TOOLS: Jupyter Notebook, MLflow, Kubeflow, AWS SageMaker, Databricks
📊 METRICS: Model accuracy, F1 score, inference latency, business impact of predictions
👥 COLLABORATES WITH: Data Engineers, Product Managers, Business Analysts
❌ DO NOT INCLUDE: Web development frameworks, frontend technologies"""

    elif any(kw in title_lower for kw in ["data engineer", "etl", "data pipeline"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR DATA ENGINEER ===
🎯 PRIMARY FOCUS: Data pipelines, ETL processes, data warehousing, data quality
📦 CORE TECHNOLOGIES: Python, SQL, Apache Spark, Airflow, Kafka, Snowflake/BigQuery
🔧 TOOLS: dbt, Great Expectations, AWS Glue, Azure Data Factory, Databricks
📊 METRICS: Pipeline reliability, data freshness, data quality scores, processing time
👥 COLLABORATES WITH: Data Scientists, Analytics Teams, Platform Engineers
❌ DO NOT INCLUDE: ML model development, frontend technologies"""

    elif any(kw in title_lower for kw in ["data analyst", "analytics"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR DATA ANALYST ===
🎯 PRIMARY FOCUS: Data analysis, reporting, business insights, visualization
📦 CORE TECHNOLOGIES: SQL, Python/R, Excel (advanced), Statistical methods
🔧 TOOLS: Tableau, Power BI, Looker, Google Analytics, Jupyter
📊 METRICS: Report accuracy, insight adoption rate, stakeholder satisfaction
👥 COLLABORATES WITH: Business Stakeholders, Data Engineers, Product Teams
❌ DO NOT INCLUDE: ML model development, infrastructure tools"""

    elif any(kw in title_lower for kw in ["security", "cybersecurity", "infosec", "penetration", "soc analyst"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR SECURITY / CYBERSECURITY ===
🎯 PRIMARY FOCUS: Threat detection, vulnerability management, security architecture
📦 CORE TECHNOLOGIES: SIEM, IDS/IPS, Firewalls, Encryption, Identity Management
🔧 TOOLS: Splunk, CrowdStrike, Nessus, Burp Suite, Wireshark, Metasploit
📊 METRICS: Incident response time, vulnerability remediation rate, security posture score
👥 COLLABORATES WITH: IT Operations, Development Teams, Compliance
❌ DO NOT INCLUDE: Application development, data science tools"""

    elif any(kw in title_lower for kw in ["cloud architect", "solutions architect", "enterprise architect"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR CLOUD/SOLUTIONS ARCHITECT ===
🎯 PRIMARY FOCUS: System design, cloud architecture, scalability, cost optimization
📦 CORE TECHNOLOGIES: AWS/GCP/Azure, Microservices, Kubernetes, Serverless
🔧 TOOLS: Draw.io, Lucidchart, Terraform, CloudFormation, Architecture frameworks
📊 METRICS: System availability, cost efficiency, scalability, architecture compliance
👥 COLLABORATES WITH: Engineering Teams, Product, Security, Leadership
✅ INCLUDE: High-level design skills, stakeholder communication"""

    elif any(kw in title_lower for kw in ["qa", "quality assurance", "test engineer", "sdet", "automation"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR QA / TEST ENGINEER ===
🎯 PRIMARY FOCUS: Test automation, quality assurance, test strategy, bug detection
📦 CORE TECHNOLOGIES: Selenium, Cypress, Jest, JUnit, TestNG, API testing
🔧 TOOLS: Postman, JMeter, BrowserStack, JIRA, TestRail, Jenkins
📊 METRICS: Test coverage, defect detection rate, automation coverage, release quality
👥 COLLABORATES WITH: Developers, Product Managers, DevOps
❌ DO NOT INCLUDE: Application development, infrastructure management"""

    elif any(kw in title_lower for kw in ["mobile", "ios", "android", "flutter", "react native"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR MOBILE DEVELOPER ===
🎯 PRIMARY FOCUS: Mobile app development, native/cross-platform, app store deployment
📦 CORE TECHNOLOGIES: Swift/Kotlin OR React Native/Flutter, REST APIs, SQLite
🔧 TOOLS: Xcode/Android Studio, Firebase, App Store Connect, TestFlight, Fastlane
📊 METRICS: App crash rate, user ratings, load time, battery efficiency
👥 COLLABORATES WITH: Backend Developers, UX Designers, Product Managers
❌ DO NOT INCLUDE: Web development frameworks, DevOps infrastructure"""

    # ===== BUSINESS / MANAGEMENT ROLES =====
    elif any(kw in title_lower for kw in ["business analyst", "ba ", "requirements analyst"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR BUSINESS ANALYST ===
🎯 PRIMARY FOCUS: Requirements gathering, process analysis, stakeholder management, solution design
📦 CORE SKILLS: BRD/FSD documentation, BPMN, UML, Use Cases, User Stories, Gap Analysis
🔧 TOOLS: Jira, Confluence, Microsoft Visio, Lucidchart, SQL, Excel (advanced), Power BI
📊 METRICS: Requirements accuracy, stakeholder satisfaction, solution adoption rate, delivery timeliness
👥 COLLABORATES WITH: Development Teams, Product Owners, Business Stakeholders, QA Teams
✅ RESPONSIBILITIES MUST INCLUDE: Requirements elicitation, process mapping, UAT coordination, stakeholder workshops
❌ DO NOT INCLUDE: Hands-on coding, infrastructure management"""

    elif any(kw in title_lower for kw in ["product manager", "product owner", "pm "]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR PRODUCT MANAGER ===
🎯 PRIMARY FOCUS: Product strategy, roadmap planning, feature prioritization, user research
📦 CORE SKILLS: Product vision, user story writing, A/B testing, competitive analysis
🔧 TOOLS: Jira, Aha!, ProductBoard, Figma, Google Analytics, Amplitude, Mixpanel
📊 METRICS: Feature adoption, user retention, NPS, revenue impact, time-to-market
👥 COLLABORATES WITH: Engineering, Design, Marketing, Sales, Customer Success
✅ INCLUDE: Strategic thinking, data-driven decision making, stakeholder alignment"""

    elif any(kw in title_lower for kw in ["project manager", "scrum master", "agile coach"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR PROJECT MANAGER / SCRUM MASTER ===
🎯 PRIMARY FOCUS: Project delivery, team facilitation, risk management, Agile ceremonies
📦 CORE SKILLS: Scrum/Kanban, project planning, resource allocation, risk mitigation
🔧 TOOLS: Jira, MS Project, Asana, Monday.com, Confluence, Miro, Teams/Slack
📊 METRICS: On-time delivery, sprint velocity, team satisfaction, scope management
👥 COLLABORATES WITH: Development Teams, Stakeholders, Leadership, Vendors
❌ DO NOT INCLUDE: Hands-on technical development"""

    elif any(kw in title_lower for kw in ["engineering manager", "tech lead", "team lead", "development manager"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR ENGINEERING MANAGER / TECH LEAD ===
🎯 PRIMARY FOCUS: Team leadership, technical direction, mentoring, delivery excellence
📦 CORE SKILLS: People management, architecture decisions, code review, sprint planning
🔧 TOOLS: GitHub, Jira, 1:1 meeting tools, performance tracking, CI/CD oversight
📊 METRICS: Team velocity, code quality, team retention, delivery predictability
👥 COLLABORATES WITH: Engineers, Product, HR, Leadership
✅ INCLUDE: Both technical expertise AND leadership/mentoring responsibilities"""

    # ===== GOVERNANCE / COMPLIANCE ROLES =====
    elif any(kw in title_lower for kw in ["governance", "compliance", "audit", "risk", "grc"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR GOVERNANCE / COMPLIANCE ===
🎯 PRIMARY FOCUS: Policy development, regulatory compliance, risk assessment, audit management
📦 CORE SKILLS: Regulatory frameworks (ISO, SOC2, GDPR), policy writing, risk assessment
🔧 TOOLS: GRC platforms, audit management tools, SharePoint, compliance tracking systems
📊 METRICS: Compliance audit scores, policy adherence rates, risk reduction, audit findings closure
👥 COLLABORATES WITH: Legal, IT Security, Operations, External Auditors, Leadership
✅ RESPONSIBILITIES MUST INCLUDE: Policy development, compliance monitoring, risk assessments, audit coordination
❌ DO NOT INCLUDE: Hands-on technical development, coding"""

    # ===== HR / RECRUITING ROLES =====
    elif any(kw in title_lower for kw in ["recruiter", "talent acquisition", "hr ", "human resource"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR HR / TALENT ACQUISITION ===
🎯 PRIMARY FOCUS: Recruitment, candidate experience, employer branding, onboarding
📦 CORE SKILLS: Sourcing, interviewing, ATS management, offer negotiation, employer branding
🔧 TOOLS: LinkedIn Recruiter, Greenhouse, Workday, BambooHR, Indeed, Glassdoor
📊 METRICS: Time-to-hire, cost-per-hire, offer acceptance rate, candidate NPS
👥 COLLABORATES WITH: Hiring Managers, HR Partners, Candidates, Agencies"""

    # ===== DESIGN ROLES =====
    elif any(kw in title_lower for kw in ["ux", "ui", "designer", "user experience", "product design"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR UX/UI DESIGNER ===
🎯 PRIMARY FOCUS: User research, wireframing, prototyping, design systems, usability testing
📦 CORE SKILLS: User-centered design, information architecture, interaction design, visual design
🔧 TOOLS: Figma, Sketch, Adobe XD, InVision, Miro, UserTesting, Hotjar
📊 METRICS: Usability scores, task completion rate, user satisfaction, design consistency
👥 COLLABORATES WITH: Product Managers, Frontend Developers, User Researchers
❌ DO NOT INCLUDE: Backend development, DevOps, data engineering"""

    # ===== SUPPORT / OPERATIONS ROLES =====
    elif any(kw in title_lower for kw in ["support", "help desk", "it support", "technical support"]):
        return """=== ROLE-SPECIFIC GUIDANCE FOR TECHNICAL SUPPORT ===
🎯 PRIMARY FOCUS: Issue resolution, customer assistance, troubleshooting, documentation
📦 CORE SKILLS: Problem diagnosis, communication, ticketing systems, technical knowledge
🔧 TOOLS: ServiceNow, Zendesk, JIRA Service Desk, Confluence, remote desktop tools
📊 METRICS: First response time, resolution time, customer satisfaction, ticket backlog
👥 COLLABORATES WITH: Engineering Teams, Product, Customers, Operations"""

    # ===== DEFAULT - Generic but helpful guidance =====
    else:
        return f"""=== ROLE-SPECIFIC GUIDANCE FOR {job_title.upper()} ===
🎯 CRITICAL: Analyze what a "{job_title}" specifically does in their day-to-day work.
📦 CORE SKILLS: List ONLY skills that are directly relevant to "{job_title}"
🔧 TOOLS: Include ONLY tools that a "{job_title}" would actually use
📊 METRICS: Define success criteria specific to "{job_title}" outcomes
👥 COLLABORATES WITH: Identify teams/stakeholders a "{job_title}" works with

⚠️ VALIDATION QUESTIONS:
1. Would someone with the title "{job_title}" actually do this task?
2. Would a "{job_title}" use this tool in their daily work?
3. Is this skill essential for a "{job_title}" to succeed?
4. Does this responsibility match the seniority level provided?

If the answer to any question is NO, do not include that item."""


def get_enterprise_extraction_prompt(text: str) -> str:
    """Get the enterprise JD extraction prompt with the text to parse."""
    return ENTERPRISE_JD_EXTRACTION_PROMPT.format(text=text[:8000])


def get_enterprise_refinement_prompt(
    current_jd: dict,
    similar_jobs_count: int = 0,
    user_requirements: str = "",
    job_level: str = ""
) -> str:
    """Get the enterprise JD refinement prompt with job_level context."""
    import json
    # Extract job_level from current_jd if not provided
    if not job_level:
        job_level = current_jd.get('job_level', 'Mid-level')
    return ENTERPRISE_JD_REFINEMENT_PROMPT.format(
        current_jd=json.dumps(current_jd, indent=2),
        similar_jobs_count=similar_jobs_count,
        user_requirements=user_requirements if user_requirements else "None",
        job_level=job_level
    )
