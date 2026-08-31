/** Map API candidate records to dashboard card shape. */

export interface DashboardCandidate {
  id: string;
  name: string;
  email: string;
  displayEmail: string | null;
  location: string;
  headline?: string;
  experience_years: number;
  skills: string[];
  active_applications: number;
  upload_date: string;
}

function skillNamesFromProfile(profile: Record<string, unknown>): string[] {
  const skills = profile.skills;
  if (Array.isArray(skills)) {
    return skills
      .map((item) => {
        if (typeof item === "string") return item.trim();
        if (item && typeof item === "object" && "name" in item) {
          return String((item as { name?: unknown }).name || "").trim();
        }
        return "";
      })
      .filter(Boolean);
  }
  if (skills && typeof skills === "object") {
    const obj = skills as Record<string, unknown>;
    const lists = ["technical_skills", "soft_skills", "tools", "languages", "certifications"];
    return lists.flatMap((key) => {
      const value = obj[key];
      if (!Array.isArray(value)) return [];
      return value.map((item) => String(item).trim()).filter(Boolean);
    });
  }
  return [];
}

function experienceYearsFromProfile(profile: Record<string, unknown>): number {
  const experience = profile.experience;
  if (experience && typeof experience === "object" && !Array.isArray(experience)) {
    const exp = experience as { total_years?: unknown };
    const total = exp.total_years;
    if (typeof total === "number" && !Number.isNaN(total)) {
      return total;
    }
    if (typeof total === "string") {
      const parsed = Number.parseFloat(total);
      if (Number.isFinite(parsed)) return parsed;
    }
  }
  const totalYears = profile.total_years_experience ?? profile.experience_years;
  if (typeof totalYears === "number" && !Number.isNaN(totalYears)) {
    return totalYears;
  }
  if (typeof totalYears === "string") {
    const parsed = Number.parseFloat(totalYears);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string {
  return value == null ? "" : String(value).trim();
}

function firstFromList(value: unknown): string {
  if (!Array.isArray(value)) return "";
  for (const item of value) {
    const text = asString(item);
    if (text) return text;
  }
  return "";
}

/** Prefer resume-parsed profile_json over stale DB columns. */
function resolveCandidateEmail(
  raw: Record<string, unknown>,
  profile: Record<string, unknown>,
): string {
  const personal = asRecord(profile.personal_info);
  return (
    firstFromList(profile.emails) ||
    asString(personal.email) ||
    asString(raw.email) ||
    asString(profile.email)
  );
}

function resolveCandidatePhone(
  raw: Record<string, unknown>,
  profile: Record<string, unknown>,
): string {
  const personal = asRecord(profile.personal_info);
  return (
    firstFromList(profile.phones) ||
    asString(personal.phone) ||
    asString(raw.phone) ||
    asString(profile.phone)
  );
}

function resolveCandidateName(
  raw: Record<string, unknown>,
  profile: Record<string, unknown>,
): string {
  const personal = asRecord(profile.personal_info);
  const profileName = profile.name;
  if (typeof profileName === "string" && profileName.trim()) return profileName.trim();
  if (profileName && typeof profileName === "object") {
    const nameObj = profileName as Record<string, unknown>;
    const structured = asString(nameObj.full_name ?? nameObj.fullName ?? nameObj.name);
    if (structured) return structured;
  }
  const fromPersonal = asString(personal.name);
  if (fromPersonal) return fromPersonal;
  return asString(raw.name) || "Unknown";
}

function resolveCandidateLocation(
  raw: Record<string, unknown>,
  profile: Record<string, unknown>,
): string {
  const personal = asRecord(profile.personal_info);
  const locationObj = profile.location;
  if (locationObj && typeof locationObj === "object" && !Array.isArray(locationObj)) {
    const loc = locationObj as Record<string, unknown>;
    const parts = [asString(loc.city), asString(loc.state), asString(loc.country)].filter(Boolean);
    if (parts.length > 0) return parts.join(", ");
  }
  const fromProfile =
    firstFromList(profile.locations) ||
    asString(personal.location) ||
    asString(profile.location);
  if (fromProfile) return fromProfile;
  return asString(raw.location);
}

function resolveCandidateHeadline(profile: Record<string, unknown>): string {
  const experience = asRecord(profile.experience);
  return asString(
    profile.headline ??
      profile.title ??
      profile.current_title ??
      profile.current_role ??
      experience.current_role,
  );
}

/** Hide synthetic upload placeholders from the UI. */
export function formatCandidateEmail(email: string): string | null {
  const trimmed = email.trim();
  if (!trimmed) return null;
  const lower = trimmed.toLowerCase();
  if (lower.endsWith("@upload.local")) return null;
  if (lower.startsWith("unknown-") && lower.includes("@")) return null;
  return trimmed;
}

export function formatCandidateUploadDate(raw?: string): string | null {
  if (!raw?.trim()) return null;
  const parsed = Date.parse(raw);
  if (!Number.isFinite(parsed)) return null;
  return new Date(parsed).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

const NAME_HONORIFICS = /^(dr|mr|mrs|ms|miss|prof|eng|sir|dame)\.?$/i;

export function getCandidateInitials(name: string): string {
  const parts = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .filter((part) => !NAME_HONORIFICS.test(part));
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

export function formatCandidateSource(source: string): string {
  const key = source.trim().toLowerCase();
  const labels: Record<string, string> = {
    resume_parsing_upload: "Resume upload",
    manual: "Manual entry",
  };
  if (labels[key]) return labels[key];
  return source
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

/** Resume-backed prompt for QuantChat — no fabricated candidate facts. */
export function buildCandidateQuantChatPrompt(candidate: CandidateDetail): string {
  const skills = candidate.skillNames.slice(0, 10).join(", ");
  const recent = candidate.experience[0];
  const recentRole = recent
    ? [recent.title, recent.company].filter(Boolean).join(" at ")
    : "";
  return [
    `Review candidate ${candidate.name} (candidate ID: ${candidate.id}).`,
    candidate.experienceYears > 0
      ? `Parsed experience: ${candidate.experienceYears} years.`
      : "",
    recentRole ? `Most recent role from resume: ${recentRole}.` : "",
    skills ? `Skills extracted from resume: ${skills}.` : "",
    "Use indexed resume data only. Summarize fit strengths, relevant experience, and fields HR should verify before shortlisting.",
  ]
    .filter(Boolean)
    .join(" ");
}

export function mapApiCandidate(raw: Record<string, unknown>): DashboardCandidate {
  const profile = asRecord(raw.profile_json);
  const email = resolveCandidateEmail(raw, profile);
  const headline = resolveCandidateHeadline(profile);

  return {
    id: String(raw.id ?? raw.candidate_id ?? ""),
    name: resolveCandidateName(raw, profile),
    email,
    displayEmail: formatCandidateEmail(email),
    location: resolveCandidateLocation(raw, profile),
    headline: headline || undefined,
    experience_years: experienceYearsFromProfile(profile),
    skills: collectSkillNamesFromProfile(profile),
    active_applications: 0,
    upload_date: String(raw.created_at ?? profile.upload_date ?? raw.updated_at ?? ""),
  };
}

export function mapCandidatesResponse(data: unknown): DashboardCandidate[] {
  if (Array.isArray(data)) {
    return data
      .filter((item) => item && typeof item === "object")
      .map((item) => mapApiCandidate(item as Record<string, unknown>));
  }
  if (data && typeof data === "object") {
    const record = data as Record<string, unknown>;
    const list = record.candidates;
    if (Array.isArray(list)) {
      return list
        .filter((item) => item && typeof item === "object")
        .map((item) => mapApiCandidate(item as Record<string, unknown>));
    }
  }
  return [];
}

/** --- Candidate detail (profile page) --- */

export interface CandidateExperienceEntry {
  company: string;
  title: string;
  location: string;
  start: string;
  end: string;
  bullets: string[];
}

export interface CandidateEducationEntry {
  degree: string;
  institution: string;
  year: string;
  field: string;
  gpa: string;
}

export interface CandidateCertificateEntry {
  name: string;
  issuer: string;
  date: string;
}

export interface CandidateSkillEntry {
  name: string;
  confidence: number | null;
  category: string;
}

export interface CandidateLinkEntry {
  label: string;
  url: string;
}

export interface CandidateDetail {
  id: string;
  name: string;
  email: string;
  displayEmail: string | null;
  phone: string | null;
  location: string;
  headline: string | null;
  summary: string | null;
  parsingConfidence: number | null;
  missingFields: string[];
  source: string | null;
  isActive: boolean;
  experienceYears: number;
  skills: CandidateSkillEntry[];
  skillNames: string[];
  experience: CandidateExperienceEntry[];
  education: CandidateEducationEntry[];
  certificates: CandidateCertificateEntry[];
  links: CandidateLinkEntry[];
  uploadedAt: string | null;
}

function isValidResumeLink(url: string): boolean {
  const trimmed = url.trim();
  if (!trimmed || trimmed === "#") return false;
  const lower = trimmed.toLowerCase();
  if (lower.startsWith("mailto:") || lower.startsWith("tel:")) return false;
  const placeholderPatterns = [
    /example\.com/i,
    /placeholder/i,
    /yourprofile/i,
    /linkedin\.com\/in\/(?:profile|username|your-name|me)\/?$/i,
    /github\.com\/(?:username|yourusername|your-name)\/?$/i,
  ];
  if (placeholderPatterns.some((pattern) => pattern.test(trimmed))) return false;
  try {
    const parsed = new URL(trimmed.startsWith("http") ? trimmed : `https://${trimmed}`);
    return Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

function normalizeLinkUrl(url: string): string {
  return url.startsWith("http") ? url : `https://${url}`;
}

function collectExperienceFromProfile(profile: Record<string, unknown>): CandidateExperienceEntry[] {
  const experienceValue = profile.experience ?? profile.work_history ?? profile.work_experience;
  if (Array.isArray(experienceValue)) {
    return mapExperienceItems(experienceValue);
  }
  const experienceRecord = asRecord(experienceValue);
  const positions = experienceRecord.positions;
  if (Array.isArray(positions)) {
    return mapExperienceItems(positions);
  }
  return [];
}

function collectEducationFromProfile(profile: Record<string, unknown>): CandidateEducationEntry[] {
  const educationValue = profile.education;
  if (Array.isArray(educationValue)) {
    return mapEducationItems(educationValue);
  }
  const educationRecord = asRecord(educationValue);
  const degrees = educationRecord.degrees;
  if (!Array.isArray(degrees)) return [];
  const institutions = educationRecord.institutions ?? educationRecord.universities;
  const graduationYears = educationRecord.graduation_years;
  const gpa = asString(educationRecord.gpa);
  return degrees
    .map((degree, index) => ({
      degree: asString(degree),
      institution: Array.isArray(institutions) ? asString(institutions[index]) : "",
      year: Array.isArray(graduationYears) ? asString(graduationYears[index]) : "",
      field: "",
      gpa: index === 0 ? gpa : "",
    }))
    .filter((entry) => entry.degree || entry.institution);
}

function collectSkillsFromProfile(profile: Record<string, unknown>): CandidateSkillEntry[] {
  const skillsValue = profile.skills;
  if (Array.isArray(skillsValue)) {
    return mapSkillEntries(skillsValue);
  }
  const skillsRecord = asRecord(skillsValue);
  const entries: CandidateSkillEntry[] = [];
  const buckets: Array<[string, string]> = [
    ["technical_skills", "technical"],
    ["soft_skills", "soft"],
    ["tools", "tool"],
    ["languages", "language"],
    ["certifications", "certification"],
  ];
  for (const [key, category] of buckets) {
    const list = skillsRecord[key];
    if (!Array.isArray(list)) continue;
    for (const item of list) {
      const name = asString(item);
      if (name) entries.push({ name, confidence: null, category });
    }
  }
  return entries;
}

function collectSkillNamesFromProfile(profile: Record<string, unknown>): string[] {
  const entries = collectSkillsFromProfile(profile);
  if (entries.length > 0) return entries.map((skill) => skill.name);
  return skillNamesFromProfile(profile);
}

function collectCertificatesFromProfile(profile: Record<string, unknown>): CandidateCertificateEntry[] {
  const direct = mapCertificateItems(
    profile.certificates ?? profile.certifications ?? profile.licenses,
  );
  if (direct.length > 0) return direct;
  const skillsRecord = asRecord(profile.skills);
  return mapCertificateItems(skillsRecord.certifications);
}

export function normalizeParsingConfidence(value: unknown): number | null {
  if (typeof value !== "number" || Number.isNaN(value)) return null;
  if (value <= 1) return Math.round(value * 100);
  return Math.round(Math.min(value, 100));
}

function mapExperienceItems(items: unknown): CandidateExperienceEntry[] {
  if (!Array.isArray(items)) return [];
  return items
    .map((raw) => {
      if (typeof raw === "string") {
        return {
          company: "",
          title: raw.trim(),
          location: "",
          start: "",
          end: "",
          bullets: [],
        };
      }
      const row = asRecord(raw);
      const bulletsRaw =
        row.bullets ?? row.responsibilities ?? row.achievements ?? row.highlights ?? row.description;
      let bullets: string[] = [];
      if (Array.isArray(bulletsRaw)) {
        bullets = bulletsRaw.map((b) => asString(b)).filter(Boolean);
      } else if (typeof bulletsRaw === "string" && bulletsRaw.trim()) {
        bullets = bulletsRaw
          .split(/\n+/)
          .map((line) => line.trim())
          .filter(Boolean);
      }
      const company = asString(
        row.company ?? row.company_name ?? row.employer ?? row.organization,
      );
      const title = asString(row.title ?? row.role ?? row.position ?? row.job_title);
      if (!company && !title) return null;
      return {
        company,
        title: title || company,
        location: asString(row.location ?? row.city),
        start: asString(row.start ?? row.start_date ?? row.from),
        end: asString(row.end ?? row.end_date ?? row.to) || "Present",
        bullets,
      };
    })
    .filter((item): item is CandidateExperienceEntry => item !== null);
}

function mapEducationItems(items: unknown): CandidateEducationEntry[] {
  if (!Array.isArray(items)) return [];
  return items
    .map((raw) => {
      if (typeof raw === "string") {
        return {
          degree: raw.trim(),
          institution: "",
          year: "",
          field: "",
          gpa: "",
        };
      }
      const row = asRecord(raw);
      const degree = asString(row.degree ?? row.qualification ?? row.program);
      const institution = asString(row.institution ?? row.school ?? row.university ?? row.college);
      if (!degree && !institution) return null;
      return {
        degree,
        institution,
        year: asString(row.year ?? row.graduation_year ?? row.dates),
        field: asString(row.field ?? row.major ?? row.specialization),
        gpa: asString(row.gpa ?? row.grade ?? row.cgpa),
      };
    })
    .filter((item): item is CandidateEducationEntry => item !== null);
}

function mapCertificateItems(items: unknown): CandidateCertificateEntry[] {
  if (!Array.isArray(items)) return [];
  return items
    .map((raw) => {
      if (typeof raw === "string") {
        return { name: raw.trim(), issuer: "", date: "" };
      }
      const row = asRecord(raw);
      const name = asString(row.name ?? row.title ?? row.certification);
      if (!name) return null;
      return {
        name,
        issuer: asString(row.issuer ?? row.organization ?? row.authority),
        date: asString(row.date ?? row.year ?? row.issued),
      };
    })
    .filter((item): item is CandidateCertificateEntry => item !== null);
}

function mapSkillEntries(items: unknown): CandidateSkillEntry[] {
  if (!Array.isArray(items)) return [];
  return items
    .map((raw) => {
      if (typeof raw === "string") {
        const name = raw.trim();
        if (!name) return null;
        return { name, confidence: null, category: "technical" };
      }
      const row = asRecord(raw);
      const name = asString(row.name ?? row.skill);
      if (!name) return null;
      const confRaw = row.confidence ?? row.score;
      const confidence =
        typeof confRaw === "number" && !Number.isNaN(confRaw)
          ? confRaw <= 1
            ? Math.round(confRaw * 100)
            : Math.round(confRaw)
          : null;
      return {
        name,
        confidence,
        category: asString(row.category) || "technical",
      };
    })
    .filter((item): item is CandidateSkillEntry => item !== null);
}

function formatLinkLabel(label: string): string {
  const key = label.trim().toLowerCase();
  if (key === "linkedin") return "LinkedIn";
  if (key === "github") return "GitHub";
  if (key === "other" || key === "link") return "Link";
  return label
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function mapLinks(profile: Record<string, unknown>): CandidateLinkEntry[] {
  const links: CandidateLinkEntry[] = [];
  const personal = asRecord(profile.personal_info);

  const pushLink = (label: string, rawUrl: string) => {
    const url = normalizeLinkUrl(rawUrl);
    if (!isValidResumeLink(url)) return;
    links.push({ label: formatLinkLabel(label), url });
  };

  const rawLinks = profile.links;
  if (Array.isArray(rawLinks)) {
    for (const item of rawLinks) {
      if (typeof item === "string" && item.trim()) {
        pushLink("Link", item.trim());
        continue;
      }
      const row = asRecord(item);
      const url = asString(row.url ?? row.href ?? row.link);
      if (!url) continue;
      const label = asString(row.type ?? row.label ?? row.name) || "Link";
      pushLink(label, url);
    }
  }

  const linkedin = asString(
    profile.linkedin ?? profile.linkedin_url ?? personal.linkedin ?? personal.linkedin_url,
  );
  if (linkedin) pushLink("LinkedIn", linkedin);

  const github = asString(
    profile.github ?? profile.github_url ?? personal.github ?? personal.github_url,
  );
  if (github) pushLink("GitHub", github);

  const website = asString(personal.website ?? personal.portfolio ?? profile.portfolio_url);
  if (website) pushLink("Website", website);

  const seen = new Set<string>();
  return links.filter((link) => {
    const key = link.url.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function collectMissingFields(
  rootMissing: unknown,
  profile: Record<string, unknown>,
): string[] {
  const fromRoot = Array.isArray(rootMissing)
    ? rootMissing.map((f) => asString(f)).filter(Boolean)
    : [];
  const screening = asRecord(profile.screening_report);
  const completeness = asRecord(profile.completeness);
  const fromProfile = [
    ...(Array.isArray(profile.missing_fields) ? profile.missing_fields : []),
    ...(Array.isArray(screening.gaps_for_hr_review) ? screening.gaps_for_hr_review : []),
    ...(Array.isArray(completeness.gaps_for_hr_review) ? completeness.gaps_for_hr_review : []),
    ...(Array.isArray(profile.ambiguous_fields) ? profile.ambiguous_fields : []),
  ]
    .map((f) => asString(f))
    .filter(Boolean);
  const merged = [...fromRoot, ...fromProfile];
  return [...new Set(merged)];
}

export function mapCandidateDetail(raw: Record<string, unknown>): CandidateDetail {
  const profile = asRecord(raw.profile_json);
  const email = resolveCandidateEmail(raw, profile);
  const headline = resolveCandidateHeadline(profile);
  const summary = asString(profile.summary ?? profile.professional_summary ?? profile.objective);
  const confidence = normalizeParsingConfidence(
    raw.parsing_confidence ?? profile.confidence ?? profile.parsing_confidence,
  );
  const experience = collectExperienceFromProfile(profile);
  const internships = mapExperienceItems(profile.internships);
  const allExperience = [...experience, ...internships];
  const skills = collectSkillsFromProfile(profile);
  const phone = resolveCandidatePhone(raw, profile);
  const location = resolveCandidateLocation(raw, profile);

  return {
    id: asString(raw.id ?? raw.candidate_id),
    name: resolveCandidateName(raw, profile),
    email,
    displayEmail: formatCandidateEmail(email),
    phone: phone || null,
    location,
    headline: headline || null,
    summary: summary || null,
    parsingConfidence: confidence,
    missingFields: collectMissingFields(raw.missing_fields, profile),
    source: asString(raw.source) || null,
    isActive: raw.is_active !== false,
    experienceYears: experienceYearsFromProfile(profile),
    skills,
    skillNames: collectSkillNamesFromProfile(profile),
    experience: allExperience,
    education: collectEducationFromProfile(profile),
    certificates: collectCertificatesFromProfile(profile),
    links: mapLinks(profile),
    uploadedAt: formatCandidateUploadDate(
      asString(raw.created_at ?? profile.upload_date ?? profile.parsed_at),
    ),
  };
}

