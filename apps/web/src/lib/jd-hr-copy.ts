/** HR-facing copy for the job description editor — no technical jargon. */

export const JD_SAVE_BUTTON_LABEL = "Save job description";

export const JD_DIALOG_TITLE_CREATE = "Create job description with AI";
export const JD_DIALOG_TITLE_EDIT = "Edit job description";

export const JD_DIALOG_DESC_CREATE =
  "Answer a few role questions and AI will draft a full job description you can review and customize.";

export const JD_DIALOG_DESC_EDIT =
  "Review and customize this job description. When you save, your jobs list, QuantChat, and matching use the updated version.";

export const JD_UNSAVED_BANNER =
  "You have unsaved changes — click Save job description to update your listing and AI search.";

export const JD_CLOSE_UNSAVED_CONFIRM =
  "You have unsaved changes to this job description. Close without saving?";

export const JD_EDIT_MODE_HINT =
  'Edit mode — update any section below, then click "Save job description" when finished.';

export const JD_SAVE_FOOTER_HINT =
  "Saving updates your job listing and makes this description searchable in QuantChat and candidate matching.";

export const JD_REGENERATE_BUTTON_LABEL = "Regenerate with AI";

export const JD_REGENERATE_CONFIRM =
  "Regenerate with AI?\n\nThis replaces the current description with a new AI draft from your HR inputs. Custom sections, hidden sections, and edits will be lost.\n\nContinue?";

export function formatJdSaveSuccessMessage(options: {
  jobTitle?: string;
  jobId: string;
  updated: boolean;
}): string {
  const title = options.jobTitle?.trim() || "Job description";
  const verb = options.updated ? "updated" : "saved";
  return `✅ "${title}" ${verb}. Your jobs list, QuantChat, and candidate matching now use this version.`;
}
