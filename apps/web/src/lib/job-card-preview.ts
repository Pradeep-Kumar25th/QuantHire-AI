import {
  ENTERPRISE_JD_SECTIONS,
  formatDepartmentTeam,
  formatLocation,
  getRemovedSectionIds,
  isEnterpriseFormat,
  type EnterpriseJobDescription,
} from "@/types/enterprise-jd";

export interface JobCardPreviewData {
  title: string;
  level?: string;
  departmentDisplay: string;
  locationLabel: string;
  workModel?: string;
  remote: boolean;
  summary?: string;
  skillTags: string[];
  customSectionCount: number;
  removedSectionCount: number;
}

const JD_PLACEHOLDER_SUMMARIES = new Set([
  "position summary will be generated.",
]);

function isPlaceholderJdSummary(value: string | undefined): boolean {
  const trimmed = (value || "").trim();
  if (!trimmed) return true;
  return JD_PLACEHOLDER_SUMMARIES.has(trimmed.toLowerCase());
}

function collectSkillTags(spec: EnterpriseJobDescription): string[] {
  const seen = new Set<string>();
  const tags: string[] = [];
  const add = (items: string[] | undefined) => {
    for (const raw of items || []) {
      const item = raw.trim();
      const key = item.toLowerCase();
      if (!item || seen.has(key)) continue;
      seen.add(key);
      tags.push(item);
      if (tags.length >= 4) return;
    }
  };
  add(spec.required_qualifications?.technical_skills);
  add(spec.tools_technologies);
  add(spec.soft_skills);
  return tags;
}

function buildEnterprisePreview(
  spec: EnterpriseJobDescription,
  job: Record<string, unknown>,
): JobCardPreviewData {
  const removed = getRemovedSectionIds(spec);
  let summary: string | undefined;
  if (!removed.includes("position_summary")) {
    const positionSummary = spec.position_summary?.trim();
    if (positionSummary && !isPlaceholderJdSummary(positionSummary)) {
      summary = positionSummary.slice(0, 180);
    }
  } else if (
    !removed.includes("responsibilities") &&
    spec.responsibilities?.[0]
  ) {
    summary = spec.responsibilities[0].trim().slice(0, 180);
  }

  const locationLabel =
    formatLocation(spec.location) ||
    String(job.location || "").trim() ||
    "Not specified";

  return {
    title: spec.job_title?.trim() || String(job.title || "Untitled Role"),
    level: spec.metadata?.job_level?.trim() || undefined,
    departmentDisplay:
      formatDepartmentTeam(spec) ||
      String(job.department || "").trim() ||
      "Not specified",
    locationLabel,
    workModel: spec.location?.work_model,
    remote:
      spec.location?.work_model === "Remote" || Boolean(job.remote_allowed),
    summary,
    skillTags: collectSkillTags(spec),
    customSectionCount: (spec.custom_sections || []).length,
    removedSectionCount: removed.length,
  };
}

/** Build card preview fields from API job payload (prefers saved enterprise JD). */
export function buildJobCardPreviewFromJob(
  job: Record<string, unknown>
): JobCardPreviewData {
  const spec = job.spec_json;
  if (isEnterpriseFormat(spec)) {
    return buildEnterprisePreview(spec, job);
  }

  return {
    title: String(job.title || "Untitled Role"),
    level: String(job.level || "").trim() || undefined,
    departmentDisplay: String(job.department || "").trim() || "Not specified",
    locationLabel: String(job.location || "").trim() || "Not specified",
    workModel: job.remote_allowed ? "Remote" : undefined,
    remote: Boolean(job.remote_allowed),
    summary: String(job.description || "").trim().slice(0, 180) || undefined,
    skillTags: [],
    customSectionCount: 0,
    removedSectionCount: 0,
  };
}

export function countVisibleEnterpriseSections(spec: EnterpriseJobDescription): number {
  const removed = new Set(getRemovedSectionIds(spec));
  return ENTERPRISE_JD_SECTIONS.filter((section) => !removed.has(section.id)).length;
}
