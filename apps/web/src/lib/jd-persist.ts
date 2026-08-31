import {
  formatLocation,
  isEnterpriseFormat,
  type EnterpriseJobDescription,
} from "@/types/enterprise-jd";

export interface JdGenerationFormSnapshot {
  job_title: string;
  job_level: string;
  department: string;
  years_of_experience: string;
  internal_title: string;
  business_unit: string;
  qualification: string;
  skills: string;
  location: string;
  remote_allowed: boolean;
  user_requirements: string;
}

export function jobHasEnterpriseJd(job: Record<string, unknown>): boolean {
  return isEnterpriseFormat(job.spec_json);
}

/** Build enterprise JD + ids from a GET /v1/jobs/{id} payload. */
export function hydrateEnterpriseJdFromJob(
  job: Record<string, unknown>
): EnterpriseJobDescription | null {
  const spec = job.spec_json;
  if (!isEnterpriseFormat(spec)) {
    return null;
  }

  const jobId = String(job.id || spec.job_id || spec.id || "");
  if (!jobId) {
    return null;
  }

  return prepareEnterpriseJdForSave({
    ...spec,
    job_id: jobId,
    id: jobId,
    milvus_id: spec.milvus_id || jobId,
    job_title: spec.job_title || String(job.title || ""),
    department: spec.department || String(job.department || ""),
  });
}

/** Restore HR form fields from saved enterprise JD metadata. */
export function buildJdGenerationFormFromJob(
  job: Record<string, unknown>,
  jd: EnterpriseJobDescription
): JdGenerationFormSnapshot {
  const metadata = jd.metadata || {};
  const dialogInputs = metadata.dialog_inputs || {};
  const hrInputs = metadata.hr_inputs || {};
  const location = jd.location;
  const locationFromJd = location
    ? [location.city, location.country].filter(Boolean).join(", ")
    : "";
  const skillsSource =
    dialogInputs.skills ||
    metadata.skills ||
    hrInputs.skills ||
    jd.required_qualifications?.technical_skills ||
    [];
  const skillsText = Array.isArray(skillsSource)
    ? skillsSource.join(", ")
    : String(skillsSource || "");

  return {
    job_title: dialogInputs.job_title || jd.job_title || String(job.title || ""),
    job_level:
      dialogInputs.job_level ||
      metadata.job_level ||
      String(job.level || ""),
    department:
      dialogInputs.department || jd.department || String(job.department || ""),
    years_of_experience:
      dialogInputs.years_of_experience ||
      metadata.years_of_experience ||
      hrInputs.years_of_experience ||
      "",
    internal_title:
      dialogInputs.internal_title ||
      metadata.internal_title ||
      hrInputs.internal_title ||
      "",
    business_unit:
      dialogInputs.business_unit ||
      metadata.business_unit ||
      hrInputs.business_unit ||
      jd.business_unit ||
      "",
    qualification:
      dialogInputs.qualification ||
      metadata.qualification ||
      hrInputs.qualification ||
      jd.required_qualifications?.education ||
      "",
    skills: skillsText,
    location:
      dialogInputs.location ||
      locationFromJd ||
      String(job.location || ""),
    remote_allowed:
      dialogInputs.remote_allowed ??
      (location?.work_model === "Remote" || Boolean(job.remote_allowed)),
    user_requirements: dialogInputs.user_requirements || "",
  };
}

/** Normalize JD payload before persisting to pgvector / jobs. */
export function prepareEnterpriseJdForSave(
  jd: EnterpriseJobDescription
): EnterpriseJobDescription {
  const cleanList = (list: string[] | undefined) =>
    (list || []).map((item) => item.trim()).filter(Boolean);

  const requiredQualifications = jd.required_qualifications || {
    education: "",
    experience: "",
    technical_skills: [],
  };
  const workEnvironment = jd.work_environment || {
    reports_to: "",
    collaborates_with: [],
  };
  const applicationInstructions = jd.application_instructions || {
    required_materials: [],
  };
  const businessUnit =
    jd.metadata?.business_unit?.trim() ||
    jd.business_unit?.trim() ||
    undefined;

  return {
    ...jd,
    metadata: {
      ...(jd.metadata || {}),
      removed_sections: [...(jd.metadata?.removed_sections || [])],
      job_level: jd.metadata?.job_level,
      internal_title: jd.metadata?.internal_title,
      business_unit: businessUnit,
      years_of_experience: jd.metadata?.years_of_experience,
      qualification: jd.metadata?.qualification,
      skills:
        jd.metadata?.skills ||
        jd.required_qualifications?.technical_skills ||
        [],
      dialog_inputs: {
        ...(jd.metadata?.dialog_inputs || {}),
        job_title: jd.job_title,
        department: jd.department,
        job_level: jd.metadata?.job_level,
        internal_title: jd.metadata?.internal_title,
        business_unit: businessUnit,
        years_of_experience: jd.metadata?.years_of_experience,
        qualification: jd.metadata?.qualification,
        skills:
          jd.metadata?.skills ||
          jd.required_qualifications?.technical_skills ||
          [],
        location: formatLocation(jd.location),
        remote_allowed: jd.location?.work_model === "Remote",
      },
    },
    responsibilities: cleanList(jd.responsibilities),
    preferred_qualifications: cleanList(jd.preferred_qualifications),
    soft_skills: cleanList(jd.soft_skills),
    tools_technologies: cleanList(jd.tools_technologies),
    success_metrics: cleanList(jd.success_metrics),
    compensation_benefits: cleanList(jd.compensation_benefits),
    required_qualifications: {
      ...requiredQualifications,
      technical_skills: cleanList(requiredQualifications.technical_skills),
    },
    work_environment: {
      ...workEnvironment,
      collaborates_with: cleanList(workEnvironment.collaborates_with),
    },
    application_instructions: {
      ...applicationInstructions,
      required_materials: cleanList(applicationInstructions.required_materials),
    },
    custom_sections: (jd.custom_sections || [])
      .map((section) => ({
        ...section,
        title: (section.title || "").trim(),
        content: (section.content || "").trim(),
      }))
      .filter((section) => section.title || section.content),
  };
}

export function resolveJdDocumentId(jd: EnterpriseJobDescription): string | null {
  return jd.job_id || jd.id || jd.milvus_id || null;
}

export function serializeJdSnapshot(jd: EnterpriseJobDescription): string {
  return JSON.stringify(prepareEnterpriseJdForSave(jd));
}

export async function persistEnterpriseJdToBackend(
  jd: EnterpriseJobDescription
): Promise<{ job_id: string; postgres_job_id?: string | null }> {
  const jdToSave = prepareEnterpriseJdForSave(jd);
  const jobIdToUse = resolveJdDocumentId(jdToSave);

  const { api } = await import("@/lib/api");
  const payloadJd = {
    ...jdToSave,
    ...(jobIdToUse
      ? { job_id: jobIdToUse, id: jobIdToUse, milvus_id: jobIdToUse }
      : {}),
  };
  const response = await api.jdGeneration.save({
    job_id: jobIdToUse || undefined,
    job_title: payloadJd.job_title,
    department: payloadJd.department,
    job_description: payloadJd,
  });

  if (response.status < 200 || response.status >= 300) {
    const detail =
      response.data?.detail ||
      response.data?.message ||
      `Save failed with status ${response.status}`;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  const savedJobId = response.data?.job_id || jobIdToUse;
  if (!savedJobId) {
    throw new Error("Save succeeded but no job_id was returned");
  }

  return {
    job_id: savedJobId,
    postgres_job_id: response.data?.postgres_job_id ?? null,
  };
}

export function notifyJobsListUpdated(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("jobsUpdated"));
  }
}
