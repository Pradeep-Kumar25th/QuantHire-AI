import type { EnterpriseJobDescription } from "@/types/enterprise-jd";

import axios from "axios";
import { apiClient } from "@/lib/api";

export type MalomatiaTemplateType = "leader" | "non_leader";

export interface MalomatiaTemplateRecommendation {
  templateType: MalomatiaTemplateType | null;
  confidence: "high" | "ambiguous" | "missing";
  reason: string;
  yoeText: string;
  yoeMinimum?: number | null;
  yoeMaximum?: number | null;
}

export const LEADER_YOE_THRESHOLD = 10;

function safeString(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}

export function collectYoeSourceText(jd: EnterpriseJobDescription): string {
  const parts: string[] = [];
  const meta = jd.metadata;

  if (meta?.years_of_experience) {
    parts.push(safeString(meta.years_of_experience));
  }
  if (meta?.hr_inputs?.years_of_experience) {
    parts.push(safeString(meta.hr_inputs.years_of_experience));
  }
  if (meta?.dialog_inputs?.years_of_experience) {
    parts.push(safeString(meta.dialog_inputs.years_of_experience));
  }
  if (jd.required_qualifications?.experience) {
    parts.push(safeString(jd.required_qualifications.experience));
  }

  return parts.filter(Boolean).join(" ");
}

interface ParsedYoe {
  minimum: number | null;
  maximum: number | null;
  hasPlus: boolean;
}

export function parseYoeDetails(text: string): ParsedYoe | null {
  const cleaned = text.trim();
  if (!cleaned) {
    return null;
  }

  const numbers = cleaned.match(/\d+/g)?.map((value) => Number.parseInt(value, 10)) ?? [];
  if (numbers.length === 0) {
    return null;
  }

  const hasPlus = /\d+\s*\+/i.test(cleaned);
  const rangeMatch = cleaned.match(/(\d+)\s*[-–—to]+\s*(\d+)/i);
  if (rangeMatch) {
    return {
      minimum: Number.parseInt(rangeMatch[1], 10),
      maximum: Number.parseInt(rangeMatch[2], 10),
      hasPlus,
    };
  }

  return {
    minimum: numbers[0],
    maximum: hasPlus ? null : numbers[0],
    hasPlus,
  };
}

export function recommendMalomatiaTemplate(
  jd: EnterpriseJobDescription
): MalomatiaTemplateRecommendation {
  const yoeText = collectYoeSourceText(jd);
  const parsed = parseYoeDetails(yoeText);

  if (!parsed || parsed.minimum == null) {
    return {
      templateType: null,
      confidence: "missing",
      reason: "Years of experience not found in the job description.",
      yoeText,
    };
  }

  const minimum = parsed.minimum;
  const maximum = parsed.maximum ?? parsed.minimum;

  if (parsed.hasPlus && minimum >= LEADER_YOE_THRESHOLD) {
    return {
      templateType: "leader",
      confidence: "high",
      reason: `Detected ${minimum}+ years of experience (Leader threshold is ${LEADER_YOE_THRESHOLD}+).`,
      yoeText,
      yoeMinimum: minimum,
      yoeMaximum: maximum,
    };
  }

  if (minimum >= LEADER_YOE_THRESHOLD) {
    return {
      templateType: "leader",
      confidence: "high",
      reason: `Detected ${minimum}${maximum !== minimum ? `–${maximum}` : ""} years of experience.`,
      yoeText,
      yoeMinimum: minimum,
      yoeMaximum: maximum,
    };
  }

  if (maximum < LEADER_YOE_THRESHOLD) {
    return {
      templateType: "non_leader",
      confidence: "high",
      reason: `Detected ${minimum}${maximum !== minimum ? `–${maximum}` : ""} years of experience (below ${LEADER_YOE_THRESHOLD}).`,
      yoeText,
      yoeMinimum: minimum,
      yoeMaximum: maximum,
    };
  }

  return {
    templateType: "leader",
    confidence: "ambiguous",
    reason: `Experience range ${minimum}–${maximum} crosses the ${LEADER_YOE_THRESHOLD}-year Leader threshold. Please confirm.`,
    yoeText,
    yoeMinimum: minimum,
    yoeMaximum: maximum,
  };
}

export function templateTypeLabel(templateType: MalomatiaTemplateType): string {
  return templateType === "leader" ? "Leader (10+ YOE)" : "Non-Leader (below 10 YOE)";
}

function filenameFromDisposition(header: string | undefined, fallback: string): string {
  if (!header) {
    return fallback;
  }
  const match = /filename="?([^";]+)"?/i.exec(header);
  return match?.[1]?.trim() || fallback;
}

export async function downloadMalomatiaTemplateDocx(
  jd: EnterpriseJobDescription,
  templateType: MalomatiaTemplateType
): Promise<void> {
  try {
    const response = await apiClient.post(
      "/v1/jd-generation/export-malomatia",
      {
        job_description: jd,
        template_type: templateType,
      },
      {
        responseType: "blob",
        headers: {
          Accept:
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
      }
    );

    const fallbackName = `${(jd.job_title || "Job_Description").replace(/[^\w.-]+/g, "_")}_Malomatia.docx`;
    const filename = filenameFromDisposition(
      typeof response.headers["content-disposition"] === "string"
        ? response.headers["content-disposition"]
        : undefined,
      fallbackName
    );

    const blob = new Blob([response.data], {
      type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    });
    const url = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(url);
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.data instanceof Blob) {
      const detailText = await error.response.data.text();
      try {
        const parsed = JSON.parse(detailText) as { detail?: string };
        if (parsed.detail) {
          throw new Error(parsed.detail);
        }
      } catch {
        if (detailText.trim()) {
          throw new Error(detailText);
        }
      }
    }
    throw error;
  }
}
