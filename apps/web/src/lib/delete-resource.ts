"use client";

import { api } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/api-errors";

export async function deleteJobWithConfirm(job: {
  id: string;
  title: string;
  applications?: number;
}): Promise<boolean> {
  const apps = job.applications ?? 0;
  if (apps > 0) {
    window.alert(
      `Cannot delete "${job.title}" because it has ${apps} application(s). Withdraw or reassign them first.`
    );
    return false;
  }

  const confirmed = window.confirm(
    `Delete "${job.title}"?\n\nThis removes the job listing and its indexed JD from QuantChat and matching. This cannot be undone.`
  );
  if (!confirmed) return false;

  try {
    await api.jobs.delete(job.id);
    if (typeof window !== "undefined") {
      sessionStorage.removeItem(`quanthire:jd-draft-${job.id}`);
      localStorage.removeItem(`quanthire:jd-draft-${job.id}`);
    }
    window.alert(`"${job.title}" deleted. It has been removed from your jobs list and QuantChat.`);
    return true;
  } catch (error: any) {
    const status = error?.response?.status;
    // 204 No Content, 200 OK, or 404 Not Found (already deleted) are successful deletions
    if (status === 204 || status === 200 || status === 404) {
      if (typeof window !== "undefined") {
        sessionStorage.removeItem(`quanthire:jd-draft-${job.id}`);
        localStorage.removeItem(`quanthire:jd-draft-${job.id}`);
      }
      window.alert(`"${job.title}" deleted.`);
      return true;
    }
    window.alert(getApiErrorMessage(error, "Failed to delete job."));
    return false;
  }
}

export async function deleteCandidateWithConfirm(candidate: {
  id: string;
  name: string;
  activeApplications?: number;
}): Promise<boolean> {
  const apps = candidate.activeApplications ?? 0;
  if (apps > 0) {
    window.alert(
      `Cannot remove "${candidate.name}" because they have ${apps} active application(s). Withdraw them first.`
    );
    return false;
  }

  const confirmed = window.confirm(
    `Remove "${candidate.name}" from the talent pool?\n\nTheir resume will be hidden and removed from QuantChat and matching. Application history must be cleared first if any exist.`
  );
  if (!confirmed) return false;

  try {
    await api.candidates.delete(candidate.id);
    window.alert(`"${candidate.name}" removed from the talent pool.`);
    return true;
  } catch (error: any) {
    const status = error?.response?.status;
    if (status === 204 || status === 200 || status === 404) {
      window.alert(`"${candidate.name}" removed from the talent pool.`);
      return true;
    }
    window.alert(getApiErrorMessage(error, "Failed to remove candidate."));
    return false;
  }
}
