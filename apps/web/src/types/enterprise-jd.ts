/**
 * Enterprise Job Description TypeScript Interfaces
 * =================================================
 * Type definitions for the 15-section Enterprise-Level Job Description format.
 */

/**
 * Work model options for job location
 */
export type WorkModel = 'On-site' | 'Hybrid' | 'Remote';

/**
 * Section 3: Location & Work Model
 */
export interface LocationModel {
  city: string;
  country: string;
  work_model: WorkModel;
  travel_required: boolean;
  travel_percentage?: number | null;
}

/**
 * Section 7: Required Qualifications with subsections
 */
export interface RequiredQualifications {
  education: string;
  experience: string;
  technical_skills: string[];
}

/**
 * Section 12: Work Environment / Reporting Structure
 */
export interface WorkEnvironment {
  reports_to: string;
  team_size?: number | null;
  collaborates_with: string[];
  collaboration_mode?: string | null;
}

/**
 * Section 15: Application Instructions
 */
export interface ApplicationInstructions {
  apply_url?: string | null;
  email?: string | null;
  required_materials: string[];
}

/**
 * Metadata for the job description
 */
export interface JDMetadata {
  generated_at?: string;
  version?: string;
  job_level?: string;
  internal_title?: string;
  business_unit?: string;
  years_of_experience?: string;
  qualification?: string;
  skills?: string[];
  removed_sections?: string[];
  hr_inputs?: {
    department?: string;
    years_of_experience?: string;
    internal_title?: string;
    business_unit?: string;
    qualification?: string;
    skills?: string[];
  };
  dialog_inputs?: {
    job_title?: string;
    job_level?: string;
    department?: string;
    years_of_experience?: string;
    internal_title?: string;
    business_unit?: string;
    qualification?: string;
    skills?: string[];
    location?: string;
    remote_allowed?: boolean;
    user_requirements?: string;
  };
  input_conformance?: {
    source?: string;
    enforced?: boolean;
    mismatches_after_enforcement?: string[];
    level_section_fixes?: string[];
    enforced_fields?: string[];
  };
  department_display?: {
    label?: string;
    value?: string;
    business_unit?: string | null;
  };
}

/**
 * User-added JD section.
 */
export interface CustomJDSection {
  id: string;
  title: string;
  content: string;
}

/**
 * Complete 15-Section Enterprise-Level Job Description
 * 
 * This interface represents the full enterprise JD format with all required sections
 * for professional, ATS-friendly job descriptions.
 */
export interface EnterpriseJobDescription {
  // Identifiers (for database operations)
  job_id?: string;
  id?: string;
  milvus_id?: string;
  
  // Section 1: Job Title
  job_title: string;
  
  // Section 2: Department / Team
  department: string;
  team?: string | null;
  division?: string | null;
  business_unit?: string | null;
  
  // Section 3: Location & Work Model
  location: LocationModel;
  
  // Section 4: About the Company
  about_company: string;
  
  // Section 5: Position Summary
  position_summary: string;
  
  // Section 6: Key Responsibilities (10-15 action-oriented bullet points)
  responsibilities: string[];
  
  // Section 7: Required Qualifications
  required_qualifications: RequiredQualifications;
  
  // Section 8: Preferred Qualifications (4-6 items)
  preferred_qualifications: string[];
  
  // Section 9: Core Competencies / Soft Skills (5-7 items)
  soft_skills: string[];
  
  // Section 10: Skills & Technologies Used
  tools_technologies: string[];
  
  // Section 11: Success Metrics / KPIs (4-6 items)
  success_metrics: string[];
  
  // Section 12: Work Environment / Reporting Structure
  work_environment: WorkEnvironment;
  
  // Section 13: Compensation & Benefits
  compensation_benefits: string[];
  
  // Section 14: Equal Opportunity Statement
  equal_opportunity_statement: string;
  
  // Section 15: Application Instructions
  application_instructions: ApplicationInstructions;

  // User-added custom sections
  custom_sections?: CustomJDSection[];
  
  // Metadata (optional)
  metadata?: JDMetadata | null;
}

/**
 * Legacy JD format for backward compatibility
 */
export interface LegacyJobDescription {
  title?: string;
  overview?: string;
  responsibilities?: string[];
  requirements?: {
    required?: string[];
    preferred?: string[];
  };
  skills?: {
    technical?: string[];
    soft?: string[];
  };
  benefits?: string[];
  sections?: Record<string, unknown>;
  custom_sections?: CustomJDSection[];
}

/**
 * Job details passed to the preview card
 */
export interface JobDetails {
  department?: string;
  location?: string;
  remote_allowed?: boolean;
  job_level?: string;
}

/**
 * Convert enterprise JD to legacy format for backward compatibility
 */
export function tolegacyFormat(jd: EnterpriseJobDescription): LegacyJobDescription {
  return {
    title: jd.job_title,
    overview: jd.position_summary,
    responsibilities: jd.responsibilities,
    requirements: {
      required: [
        jd.required_qualifications.education,
        jd.required_qualifications.experience,
        ...jd.required_qualifications.technical_skills
      ],
      preferred: jd.preferred_qualifications
    },
    skills: {
      technical: jd.tools_technologies,
      soft: jd.soft_skills
    },
    benefits: jd.compensation_benefits,
    sections: {
      about_company: jd.about_company,
      success_metrics: jd.success_metrics,
      work_environment: jd.work_environment,
      equal_opportunity: jd.equal_opportunity_statement,
      application_instructions: jd.application_instructions
    }
  };
}

/**
 * Check if a JD object is in enterprise format
 */
export function isEnterpriseFormat(jd: unknown): jd is EnterpriseJobDescription {
  if (!jd || typeof jd !== 'object') return false;
  const obj = jd as Record<string, unknown>;
  return (
    'job_title' in obj &&
    'location' in obj &&
    'about_company' in obj &&
    'position_summary' in obj &&
    'required_qualifications' in obj &&
    'work_environment' in obj &&
    'equal_opportunity_statement' in obj &&
    'application_instructions' in obj
  );
}

/** Standard enterprise JD sections in display order (matches HITL UI). */
export const ENTERPRISE_JD_SECTIONS: ReadonlyArray<{ id: string; label: string }> = [
  { id: "job_title", label: "Job Title" },
  { id: "department_team", label: "Department / Grade / BU" },
  { id: "location_work_model", label: "Location & Work Model" },
  { id: "about_company", label: "About the Company" },
  { id: "position_summary", label: "Position Summary" },
  { id: "responsibilities", label: "Key Responsibilities" },
  { id: "required_qualifications", label: "Required Qualifications" },
  { id: "preferred_qualifications", label: "Preferred Qualifications" },
  { id: "soft_skills", label: "Core Competencies / Soft Skills" },
  { id: "tools_technologies", label: "Skills & Technologies" },
  { id: "success_metrics", label: "Success Metrics / KPIs" },
  { id: "work_environment", label: "Work Environment / Reporting Structure" },
  { id: "compensation_benefits", label: "Compensation & Benefits" },
  { id: "equal_opportunity_statement", label: "Equal Opportunity Statement" },
  { id: "application_instructions", label: "Application Instructions" },
];

export function getRemovedSectionIds(jd: EnterpriseJobDescription): string[] {
  return jd.metadata?.removed_sections || [];
}

/** Assign contiguous numbers (1..N) to visible standard sections only. */
export function buildVisibleSectionNumberMap(
  jd: EnterpriseJobDescription
): Map<string, number> {
  const removed = new Set(getRemovedSectionIds(jd));
  const map = new Map<string, number>();
  let number = 1;
  for (const section of ENTERPRISE_JD_SECTIONS) {
    if (!removed.has(section.id)) {
      map.set(section.id, number++);
    }
  }
  return map;
}

export function getVisibleSectionNumber(
  jd: EnterpriseJobDescription,
  sectionId: string
): number | null {
  return buildVisibleSectionNumberMap(jd).get(sectionId) ?? null;
}

export function getCustomSectionNumber(
  jd: EnterpriseJobDescription,
  customIndex: number
): number {
  return buildVisibleSectionNumberMap(jd).size + 1 + customIndex;
}

export function formatNumberedSectionLabel(
  jd: EnterpriseJobDescription,
  sectionId: string,
  title: string
): string {
  const number = getVisibleSectionNumber(jd, sectionId);
  return number ? `${number}. ${title}` : title;
}

/**
 * Malomatia company information - used as default for all JDs
 */
export const MALOMATIA_COMPANY_INFO = {
  about_company: "Malomatia is a leading provider of Information Technology services and solutions headquartered in Doha, Qatar, delivering digital transformation, managed services, and operational excellence across multiple sectors and delivery locations. Founded in 2008 at Manarat Lusail Tower, Malomatia supports Qatar's National Vision 2030 while enabling clients through reliable technology services, process improvement, and knowledge-based innovation.",
  equal_opportunity_statement: "Malomatia is an Equal Opportunity Employer. We celebrate diversity and are committed to creating an inclusive environment for all employees regardless of race, religion, gender, age, nationality, disability, or any other protected status. We welcome applications from all qualified candidates.",
  default_location: {
    city: 'Location to be confirmed',
    country: '',
    work_model: 'Hybrid' as const,
    travel_required: false
  },
  application_instructions: {
    apply_url: 'https://careers.malomatia.com/apply',
    email: 'careers@malomatia.com',
    required_materials: ['Resume', 'Cover Letter']
  }
};

/**
 * Detect HR grade/band codes such as A2, B3, or C1.
 */
export function isHrGradeCode(value?: string | null): boolean {
  return /^[A-Z]{1,3}\d{1,3}$/.test((value || '').trim());
}

/**
 * Return the best section label for the HR matrix organization fields.
 */
export function getDepartmentSectionLabel(jd: EnterpriseJobDescription): string {
  return isHrGradeCode(jd.department) ? 'Grade / Business Unit' : 'Department / Team';
}

/**
 * Format Department/Grade/BU values without losing the exact HR matrix input.
 */
export function formatDepartmentTeam(
  jd: EnterpriseJobDescription,
  options: { labeled?: boolean } = {}
): string {
  const department = (jd.department || '').trim();
  const businessUnit = (jd.business_unit || jd.metadata?.business_unit || jd.division || '').trim();
  const team = (jd.team || '').trim();
  const division = (jd.division || '').trim();
  const labeled = options.labeled === true;

  if (isHrGradeCode(department)) {
    const parts = labeled ? [`Grade/Band: ${department}`] : [department];
    if (businessUnit) {
      parts.push(labeled ? `Business Unit: ${businessUnit}` : businessUnit);
    }
    return parts.filter(Boolean).join(' / ');
  }

  const parts = [department, team, division || businessUnit]
    .filter(Boolean)
    .filter((value, index, values) => values.indexOf(value) === index);
  return parts.join(labeled ? ' / ' : ' / ');
}

/**
 * True when the JD intentionally avoids inventing a location.
 */
export function isLocationToBeConfirmed(location?: LocationModel | null): boolean {
  const city = (location?.city || '').trim().toLowerCase();
  const country = (location?.country || '').trim().toLowerCase();
  return (!city && !country) || city === 'location to be confirmed' || city === 'to be confirmed';
}

/**
 * Create default enterprise JD with Malomatia company values
 */
export function createDefaultEnterpriseJD(
  jobTitle: string = 'Job Title',
  department: string = 'Department'
): EnterpriseJobDescription {
  return {
    job_title: jobTitle,
    department: department,
    location: MALOMATIA_COMPANY_INFO.default_location,
    about_company: MALOMATIA_COMPANY_INFO.about_company,
    position_summary: 'Position summary will be generated.',
    responsibilities: [],
    required_qualifications: {
      education: 'Bachelor\'s degree in relevant field',
      experience: '3+ years of relevant experience',
      technical_skills: []
    },
    preferred_qualifications: [],
    soft_skills: [],
    tools_technologies: [],
    success_metrics: [],
    work_environment: {
      reports_to: 'Manager',
      collaborates_with: []
    },
    compensation_benefits: [],
    equal_opportunity_statement: MALOMATIA_COMPANY_INFO.equal_opportunity_statement,
    application_instructions: MALOMATIA_COMPANY_INFO.application_instructions
  };
}

/**
 * Format location for display
 */
export function formatLocation(location: LocationModel): string {
  if (isLocationToBeConfirmed(location)) {
    return 'Location to be confirmed';
  }

  const place = [location.city, location.country].filter(Boolean).join(', ');
  let result = place ? `${place} - ${location.work_model}` : location.work_model;
  if (location.travel_required) {
    const pct = location.travel_percentage ? `${location.travel_percentage}%` : 'Yes';
    result += ` | Travel Required: ${pct}`;
  }
  return result;
}

/**
 * Format work environment for display
 */
export function formatWorkEnvironmentLines(env: WorkEnvironment): string[] {
  const parts = [`Reports to: ${env.reports_to}`];
  if (env.team_size) parts.push(`Team size: ${env.team_size}`);
  if (env.collaborates_with.length > 0) {
    parts.push(`Collaborates with: ${env.collaborates_with.join(', ')}`);
  }
  if (env.collaboration_mode) parts.push(`Mode: ${env.collaboration_mode}`);
  return parts;
}

/**
 * Format work environment for compact display.
 */
export function formatWorkEnvironment(env: WorkEnvironment): string {
  return formatWorkEnvironmentLines(env).join(' | ');
}

/**
 * Format application instructions for display
 */
export function formatApplicationInstructions(instructions: ApplicationInstructions): string {
  const parts: string[] = [];
  if (instructions.apply_url) parts.push(`Apply at: ${instructions.apply_url}`);
  if (instructions.email) parts.push(`Email: ${instructions.email}`);
  if (instructions.required_materials.length > 0) {
    parts.push(`Include: ${instructions.required_materials.join(', ')}`);
  }
  return parts.length > 0 ? parts.join(' | ') : 'Contact HR for details';
}
