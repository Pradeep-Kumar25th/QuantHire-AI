/**
 * Enterprise JD Print HTML Generator
 * ===================================
 * Generates print-friendly HTML for the 15-section Enterprise Job Description.
 */

import type { EnterpriseJobDescription } from "@/types/enterprise-jd";
import {
  formatApplicationInstructions,
  formatDepartmentTeam,
  formatLocation,
  formatWorkEnvironmentLines,
  getDepartmentSectionLabel,
} from "@/types/enterprise-jd";

/**
 * Common spacing corrections for technology terms
 * Matches the backend TECH_TERM_CORRECTIONS dictionary
 */
const TECH_TERM_CORRECTIONS: Record<string, string> = {
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
  'ML flow': 'MLflow',
  'ml flow': 'MLflow',
  'Lang Chain': 'LangChain',
  'lang chain': 'LangChain',
  'Llama Index': 'LlamaIndex',
  'llama index': 'LlamaIndex',
  'Spa Cy': 'spaCy',
  'spa cy': 'spaCy',
  'A / B': 'A/B',
  'Open AI': 'OpenAI',
  'open ai': 'OpenAI',
  'CI / CD': 'CI/CD',
  'Dev Ops': 'DevOps',
  'dev ops': 'DevOps',
  'Py Charm': 'PyCharm',
  'F 1-score': 'F1-score',
  'F 1 score': 'F1-score',
  'F1 - score': 'F1-score',
  'KPI s': 'KPIs',
  'AUC - ROC': 'AUC-ROC',
  'https: / /': 'https://',
  'https:// ': 'https://',
  'http: / /': 'http://',
  'http:// ': 'http://',
  '. com / ': '.com/',
  '.com / ': '.com/',
  ' / apply': '/apply',
  'Mule Soft': 'MuleSoft',
  'mule soft': 'MuleSoft',
  'Swagger / Open API': 'Swagger/OpenAPI',
  'Swagger / OpenAPI': 'Swagger/OpenAPI',
  'Open API': 'OpenAPI',
  'ESB / ': 'ESB/',
  'ggplot 2': 'ggplot2',
  'Deep Speed': 'DeepSpeed',
  'RAG s': 'RAGs',
  'API s': 'APIs',
  'GPU s': 'GPUs',
  'CPU s': 'CPUs',
};

/**
 * Normalize technology terms by fixing common spacing issues
 */
function normalizeTechTerms(text: string): string {
  if (!text) return '';
  let result = text;
  for (const [incorrect, correct] of Object.entries(TECH_TERM_CORRECTIONS)) {
    result = result.split(incorrect).join(correct);
  }
  return result;
}

/**
 * Escape HTML special characters to prevent XSS and display issues
 */
function escapeHtml(text: string): string {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Decode HTML entities and then escape for safe display
 * Also normalizes tech terms to fix spacing issues
 */
function sanitizeText(text: string): string {
  if (!text) return '';
  
  // Create a temporary element to decode HTML entities
  const textarea = document.createElement('textarea');
  textarea.innerHTML = text;
  const decoded = textarea.value;
  
  // Normalize tech terms to fix spacing issues like "Num Py" -> "NumPy"
  const normalized = normalizeTechTerms(decoded);
  
  // Now escape it properly for HTML display
  return escapeHtml(normalized);
}

/**
 * Generate print-friendly HTML for Enterprise JD - Clean Professional Format
 */
export function generateEnterprisePrintHTML(jd: EnterpriseJobDescription): string {
  // Use plain text separator instead of unicode arrow to prevent encoding issues
  const deptTeam = formatDepartmentTeam(jd);
  const departmentSectionLabel = getDepartmentSectionLabel(jd);
  const workEnvironment = formatWorkEnvironmentLines(jd.work_environment)
    .map((line) => `<div>${sanitizeText(line)}</div>`)
    .join('');
  
  return `
    <!DOCTYPE html>
    <html>
    <head>
      <title>${jd.job_title} - Job Description</title>
      <style>
        * { box-sizing: border-box; }
        body { 
          font-family: 'Segoe UI', Arial, sans-serif; 
          padding: 40px; 
          max-width: 900px; 
          margin: 0 auto; 
          color: #333;
          line-height: 1.6;
          letter-spacing: normal;
        }
        .header { 
          border-bottom: 2px solid #333;
          padding-bottom: 20px;
          margin-bottom: 30px;
        }
        .header h1 { margin: 0 0 10px 0; font-size: 26px; color: #000; letter-spacing: normal; }
        .header .meta { color: #555; font-size: 14px; letter-spacing: normal; }
        .section { margin-bottom: 25px; page-break-inside: avoid; }
        .section-header { 
          border-bottom: 1px solid #333;
          padding-bottom: 5px;
          margin-bottom: 12px;
          font-weight: bold;
          font-size: 14px;
          color: #000;
          letter-spacing: normal;
        }
        .section-number { 
          font-weight: bold;
          margin-right: 8px;
        }
        .content { padding: 0; letter-spacing: normal; }
        ul { margin: 10px 0; padding-left: 25px; }
        li { margin: 6px 0; color: #333; letter-spacing: normal; }
        .skills { margin: 10px 0; }
        .skill-item { 
          display: inline-block;
          margin: 3px 8px 3px 0;
          color: #333;
          letter-spacing: normal;
        }
        .subsection { margin: 10px 0; }
        .subsection-title { font-weight: bold; color: #333; margin-bottom: 5px; letter-spacing: normal; }
        .eeo { 
          padding: 15px; 
          border: 1px solid #ccc;
          font-size: 13px;
          margin-top: 10px;
          letter-spacing: normal;
        }
        .apply-box { 
          padding: 15px; 
          border: 1px solid #ccc;
          margin-top: 10px;
          letter-spacing: normal;
        }
        .footer { 
          margin-top: 40px; 
          text-align: center; 
          color: #666; 
          font-size: 10px; 
          border-top: 1px solid #ccc; 
          padding-top: 15px;
          letter-spacing: normal;
        }
        @media print { 
          body { padding: 20px; }
          .section { page-break-inside: avoid; }
        }
      </style>
    </head>
    <body>
      <div class="header">
        <h1>${sanitizeText(jd.job_title)}</h1>
        <div class="meta">${sanitizeText(deptTeam)} | ${formatLocation(jd.location)}</div>
      </div>
      
      <!-- Section 1: Job Title -->
      <div class="section">
        <div class="section-header"><span class="section-number">1.</span>Job Title</div>
        <div class="content"><strong>${sanitizeText(jd.job_title)}</strong></div>
      </div>
      
      <!-- Section 2: Department / Team -->
      <div class="section">
        <div class="section-header"><span class="section-number">2.</span>${sanitizeText(departmentSectionLabel)}</div>
        <div class="content">${sanitizeText(formatDepartmentTeam(jd, { labeled: true }))}</div>
      </div>
      
      <!-- Section 3: Location & Work Model -->
      <div class="section">
        <div class="section-header"><span class="section-number">3.</span>Location & Work Model</div>
        <div class="content">${formatLocation(jd.location)}</div>
      </div>
      
      <!-- Section 4: About the Company -->
      <div class="section">
        <div class="section-header"><span class="section-number">4.</span>About the Company</div>
        <div class="content">${sanitizeText(jd.about_company)}</div>
      </div>
      
      <!-- Section 5: Position Summary -->
      <div class="section">
        <div class="section-header"><span class="section-number">5.</span>Position Summary</div>
        <div class="content">${sanitizeText(jd.position_summary)}</div>
      </div>
      
      <!-- Section 6: Key Responsibilities -->
      <div class="section">
        <div class="section-header"><span class="section-number">6.</span>Key Responsibilities</div>
        <div class="content">
          <ul>${jd.responsibilities.map(r => `<li>${sanitizeText(r)}</li>`).join('')}</ul>
        </div>
      </div>
      
      <!-- Section 7: Required Qualifications -->
      <div class="section">
        <div class="section-header"><span class="section-number">7.</span>Required Qualifications</div>
        <div class="content">
          <div class="subsection">
            <div class="subsection-title">Qualification:</div>
            ${sanitizeText(jd.required_qualifications.education)}
          </div>
          <div class="subsection">
            <div class="subsection-title">Experience:</div>
            ${sanitizeText(jd.required_qualifications.experience)}
          </div>
          <div class="subsection">
            <div class="subsection-title">Skills:</div>
            <div class="skills">
              ${jd.required_qualifications.technical_skills.map(s => `<span class="skill-item">• ${sanitizeText(s)}</span>`).join('')}
            </div>
          </div>
        </div>
      </div>
      
      <!-- Section 8: Preferred Qualifications -->
      <div class="section">
        <div class="section-header"><span class="section-number">8.</span>Preferred Qualifications</div>
        <div class="content">
          <ul>${jd.preferred_qualifications.map(p => `<li>${sanitizeText(p)}</li>`).join('')}</ul>
        </div>
      </div>
      
      <!-- Section 9: Core Competencies -->
      <div class="section">
        <div class="section-header"><span class="section-number">9.</span>Core Competencies / Soft Skills</div>
        <div class="content">
          <div class="skills">
            ${jd.soft_skills.map(s => `<span class="skill-item">• ${sanitizeText(s)}</span>`).join('')}
          </div>
        </div>
      </div>
      
      <!-- Section 10: Skills & Technologies -->
      <div class="section">
        <div class="section-header"><span class="section-number">10.</span>Skills & Technologies</div>
        <div class="content">
          <div class="skills">
            ${jd.tools_technologies.map(t => `<span class="skill-item">• ${sanitizeText(t)}</span>`).join('')}
          </div>
        </div>
      </div>
      
      <!-- Section 11: Success Metrics -->
      <div class="section">
        <div class="section-header"><span class="section-number">11.</span>Success Metrics / KPIs</div>
        <div class="content">
          <ul>${jd.success_metrics.map(m => `<li>${sanitizeText(m)}</li>`).join('')}</ul>
        </div>
      </div>
      
      <!-- Section 12: Work Environment -->
      <div class="section">
        <div class="section-header"><span class="section-number">12.</span>Work Environment / Reporting Structure</div>
        <div class="content">${workEnvironment}</div>
      </div>
      
      <!-- Section 13: Compensation & Benefits -->
      <div class="section">
        <div class="section-header"><span class="section-number">13.</span>Compensation & Benefits</div>
        <div class="content">
          <ul>${jd.compensation_benefits.map(b => `<li>${sanitizeText(b)}</li>`).join('')}</ul>
        </div>
      </div>
      
      <!-- Section 14: Equal Opportunity Statement -->
      <div class="section">
        <div class="section-header"><span class="section-number">14.</span>Equal Opportunity Statement</div>
        <div class="content">
          <div class="eeo">${sanitizeText(jd.equal_opportunity_statement)}</div>
        </div>
      </div>
      
      <!-- Section 15: Application Instructions -->
      <div class="section">
        <div class="section-header"><span class="section-number">15.</span>Application Instructions</div>
        <div class="content">
          <div class="apply-box">${formatApplicationInstructions(jd.application_instructions)}</div>
        </div>
      </div>
      
      <div class="footer">
        Generated by QuantHire AI
      </div>
    </body>
    </html>
  `;
}

/**
 * Open print dialog with enterprise JD
 */
export function printEnterpriseJD(jd: EnterpriseJobDescription): void {
  const printContent = generateEnterprisePrintHTML(jd);
  const printWindow = window.open('', '_blank');
  if (printWindow) {
    printWindow.document.write(printContent);
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 250);
  }
}
