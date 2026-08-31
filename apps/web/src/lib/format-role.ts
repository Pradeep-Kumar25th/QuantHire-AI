/** Format QuantHire RBAC role for UI (matches Entra app role labels). */

const ROLE_LABELS: Record<string, string> = {
  admin: "ADMIN",
  recruiter: "RECRUITER",
  hiring_manager: "HIRING_MANAGER",
  interviewer: "INTERVIEWER",
  viewer: "VIEWER",
  candidate: "CANDIDATE",
  // Defensive: accept uppercase JWT/Entra spellings if ever returned raw.
  ADMIN: "ADMIN",
  RECRUITER: "RECRUITER",
  HIRING_MANAGER: "HIRING_MANAGER",
  INTERVIEWER: "INTERVIEWER",
  VIEWER: "VIEWER",
  CANDIDATE: "CANDIDATE",
};

export function formatRoleLabel(role: string | null | undefined): string {
  if (!role) {
    return "";
  }
  const trimmed = role.trim();
  if (ROLE_LABELS[trimmed]) {
    return ROLE_LABELS[trimmed];
  }
  const normalized = trimmed.toLowerCase();
  if (ROLE_LABELS[normalized]) {
    return ROLE_LABELS[normalized];
  }
  return normalized.replace(/_/g, " ").toUpperCase();
}
