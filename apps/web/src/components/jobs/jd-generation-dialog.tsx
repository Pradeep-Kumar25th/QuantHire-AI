"use client";

import { useState, useEffect, useRef } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import {
  Loader2,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Briefcase,
  Building2,
  GraduationCap,
  SlidersHorizontal,
} from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { JDPreviewCard } from "./jd-preview-card";
import { AZURE_BACKEND_HINT } from "@/lib/azure-messages";
import type { EnterpriseJobDescription } from "@/types/enterprise-jd";
import { isEnterpriseFormat } from "@/types/enterprise-jd";
import {
  notifyJobsListUpdated,
  persistEnterpriseJdToBackend,
  prepareEnterpriseJdForSave,
  buildJdGenerationFormFromJob,
  hydrateEnterpriseJdFromJob,
  type JdGenerationFormSnapshot,
} from "@/lib/jd-persist";
import {
  JD_CLOSE_UNSAVED_CONFIRM,
  JD_DIALOG_DESC_CREATE,
  JD_DIALOG_DESC_EDIT,
  JD_DIALOG_TITLE_CREATE,
  JD_DIALOG_TITLE_EDIT,
  JD_REGENERATE_BUTTON_LABEL,
  JD_REGENERATE_CONFIRM,
  JD_UNSAVED_BANNER,
} from "@/lib/jd-hr-copy";

interface JDGenerationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onJDGenerated?: (jd: any) => void;
  /** When set, opens saved JD in preview/HITL edit mode instead of the generate form. */
  editJobId?: string | null;
}

interface AgentThought {
  agent: string;
  thought: string;
  action?: string;
  state?: string;
  reasoning?: any;
  autonomous?: boolean;
}

interface JDGenerationResponse {
  job_description?: any;
  jd?: any;
  job_id?: string;
  postgres_job_id?: string;
  milvus_id?: string;
  vector_id?: string;
  storage_backend?: string;
  agent_thoughts: AgentThought[];
  success: boolean;
  error?: string;
}

const INITIAL_FORM_DATA: JdGenerationFormSnapshot = {
  job_title: "",
  job_level: "",
  department: "",
  years_of_experience: "",
  internal_title: "",
  business_unit: "",
  qualification: "",
  skills: "",
  location: "",
  remote_allowed: false,
  user_requirements: "",
};

const JD_DRAFT_JOB_ID_KEY = "quanthire:jd-draft-job-id";

function readDraftJobId(): string | null {
  if (typeof window === "undefined") return null;
  const value = sessionStorage.getItem(JD_DRAFT_JOB_ID_KEY);
  return value?.trim() || null;
}

function writeDraftJobId(jobId: string | null | undefined) {
  if (typeof window === "undefined") return;
  const normalized = jobId?.trim();
  if (normalized) sessionStorage.setItem(JD_DRAFT_JOB_ID_KEY, normalized);
  else sessionStorage.removeItem(JD_DRAFT_JOB_ID_KEY);
}

export function JDGenerationDialog({
  open,
  onOpenChange,
  onJDGenerated,
  editJobId = null,
}: JDGenerationDialogProps) {
  const [loading, setLoading] = useState(false);
  const [loadingExisting, setLoadingExisting] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [formData, setFormData] = useState<JdGenerationFormSnapshot>(INITIAL_FORM_DATA);
  const [generatedJD, setGeneratedJD] = useState<any>(null);
  const [agentThoughts, setAgentThoughts] = useState<AgentThought[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("form");
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  const [connectionMessage, setConnectionMessage] = useState<string | null>(null);
  const [editedJD, setEditedJD] = useState<any>(null);
  const [generationProgress, setGenerationProgress] = useState<string | null>(null);
  const [hasUnsavedEdits, setHasUnsavedEdits] = useState(false);
  const [dialogMode, setDialogMode] = useState<"create" | "edit">("create");
  /** When set, generate/save updates this job row instead of creating duplicates. */
  const [replaceJobId, setReplaceJobId] = useState<string | null>(null);
  const generationInFlightRef = useRef(false);

  const resolveReplaceJobId = (...candidates: Array<string | null | undefined>) => {
    for (const candidate of [readDraftJobId(), ...candidates]) {
      if (candidate && String(candidate).trim()) {
        return String(candidate).trim();
      }
    }
    return null;
  };

  const resetCreateDialogState = () => {
    setFormData(INITIAL_FORM_DATA);
    setGeneratedJD(null);
    setEditedJD(null);
    setAgentThoughts([]);
    setError(null);
    setActiveTab("form");
    setHasUnsavedEdits(false);
    setGenerationProgress(null);
    setGenerating(false);
    setLoadingExisting(false);
    setDialogMode("create");
    setReplaceJobId(readDraftJobId());
  };

  const resetDialogState = () => {
    resetCreateDialogState();
    setReplaceJobId(null);
  };

  const isEditMode = dialogMode === "edit";

  const requestDialogClose = () => {
    if (hasUnsavedEdits && !window.confirm(JD_CLOSE_UNSAVED_CONFIRM)) {
      return;
    }
    onOpenChange(false);
  };

  const handleDialogOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) {
      requestDialogClose();
      return;
    }
    onOpenChange(true);
  };

  useEffect(() => {
    if (!open) {
      resetDialogState();
      return;
    }

    if (!editJobId) {
      resetCreateDialogState();
      setDialogMode("create");
      return;
    }

    let cancelled = false;

    const loadExistingJob = async () => {
      setLoadingExisting(true);
      setError(null);
      setDialogMode("edit");

      try {
        const { api } = await import("@/lib/api");
        const response = await api.jobs.get(editJobId);
        if (cancelled) return;

        const job = response.data as Record<string, unknown>;
        const jd = hydrateEnterpriseJdFromJob(job);
        if (!jd) {
          setError(
            "This job does not have a saved AI enterprise JD. Use the job detail page for basic edits."
          );
          setDialogMode("create");
          setActiveTab("form");
          return;
        }

        setFormData(buildJdGenerationFormFromJob(job, jd));
        setGeneratedJD(jd);
        setEditedJD(jd);
        setReplaceJobId(resolveReplaceJobId(editJobId, jd.job_id, jd.id));
        setAgentThoughts([]);
        setHasUnsavedEdits(false);
        setActiveTab("preview");
      } catch (loadError) {
        console.error("Failed to load saved JD:", loadError);
        if (!cancelled) {
          setError("Failed to load the saved job description. Please try again.");
          setActiveTab("form");
          setDialogMode("create");
        }
      } finally {
        if (!cancelled) {
          setLoadingExisting(false);
        }
      }
    };

    void loadExistingJob();

    return () => {
      cancelled = true;
    };
  }, [open, editJobId]);

  // Check backend connection when dialog opens
  useEffect(() => {
    if (!open) return;
    
    const checkConnection = async () => {
      try {
        const { testBackendConnection } = await import('@/lib/api-health');
        const result = await testBackendConnection();
        setBackendConnected(result.success);
        if (!result.success) {
          setConnectionMessage(result.message);
        } else {
          setConnectionMessage(null);
        }
      } catch (err) {
        console.error('Failed to check backend connection:', err);
        setBackendConnected(false);
        setConnectionMessage('Unable to verify backend connection');
      }
    };
    
    checkConnection();
  }, [open]);

  const splitSkills = (value: string): string[] =>
    value
      .split(/[\n,]+/)
      .map((skill) => skill.trim())
      .filter(Boolean);

  const getEffectiveJobTitle = (): string =>
    (formData.job_title || formData.internal_title).trim();

  const getEffectiveJobLevel = (): string => {
    const explicit = formData.job_level.trim();
    const explicitLower = explicit.toLowerCase();
    const title = `${formData.job_title} ${formData.internal_title}`.toLowerCase();
    const years = formData.years_of_experience.trim();
    const normalizedYears = years.toLowerCase().replace(/\s+/g, "");
    const yearNumbers = (years.match(/\d+(?:\.\d+)?/g) || []).map(Number);
    const minYears = yearNumbers[0];
    const maxYears = yearNumbers.length > 1 ? yearNumbers[1] : yearNumbers[0];
    const isDefaultLikeMid = ["mid", "mid-level", "mid level", "midlevel", "middle"].includes(explicitLower);

    if (explicit && !isDefaultLikeMid) return explicit;
    if (title.includes("trainee") || title.includes("intern") || normalizedYears.startsWith("0-1")) {
      return "Entry-level";
    }
    if (title.includes("principal")) return "Principal";
    if (title.includes("architect")) return "Architect";
    if (title.includes("lead")) return "Lead";
    if (title.includes("senior")) return "Senior";
    if (title.includes("consultant")) return "Consultant";
    if (title.includes("associate") || normalizedYears.startsWith("1-3")) {
      return "Associate";
    }
    if (title.includes("junior") || normalizedYears.startsWith("2-4")) {
      return "Junior";
    }
    if (yearNumbers.length > 0 && !Number.isNaN(minYears) && !Number.isNaN(maxYears)) {
      if (maxYears <= 1) return "Entry-level";
      if (minYears <= 1 && maxYears <= 3) return "Associate";
      if (minYears >= 12) return "Principal";
      if (minYears >= 9) return "Senior";
    }
    if (explicit) return explicit;
    return "Mid-level";
  };

  const getDisplayedJobLevel = (): string => {
    if (
      !formData.job_title.trim() &&
      !formData.internal_title.trim() &&
      !formData.years_of_experience.trim()
    ) {
      return "Pending";
    }
    return getEffectiveJobLevel();
  };

  const formatExperience = (value: string): string => {
    const cleaned = value.trim();
    if (!cleaned) return "";
    if (/years?|yrs?/i.test(cleaned)) return cleaned;
    return `${cleaned} years of relevant experience`;
  };

  const getMissingBusinessReadyInputs = (): string[] => {
    const missing: string[] = [];
    if (!getEffectiveJobTitle()) missing.push("JD Title or Internal Title");
    if (!formData.department.trim()) missing.push("Department");
    if (!formData.years_of_experience.trim()) missing.push("Years of Exp");
    if (!formData.internal_title.trim()) missing.push("Internal Title");
    if (!formData.qualification.trim()) missing.push("Qualification");
    if (splitSkills(formData.skills).length === 0) missing.push("Skills");
    return missing;
  };

  const applyHrInputsToJD = (sourceJD: any) => {
    if (!sourceJD || typeof sourceJD !== "object") return sourceJD;

    const updatedJD = { ...sourceJD };
    const skillsList = splitSkills(formData.skills);
    const metadata = { ...(updatedJD.metadata || {}) };
    const effectiveJobTitle = getEffectiveJobTitle();
    const effectiveJobLevel = getEffectiveJobLevel();

    if (effectiveJobTitle) {
      updatedJD.job_title = effectiveJobTitle;
    }

    if (formData.department.trim()) {
      updatedJD.department = formData.department.trim();
    }

    metadata.job_level = effectiveJobLevel;

    metadata.hr_inputs = {
      ...(metadata.hr_inputs || {}),
      department: formData.department.trim() || undefined,
      years_of_experience: formData.years_of_experience.trim() || undefined,
      internal_title: formData.internal_title.trim() || undefined,
      business_unit: formData.business_unit.trim() || undefined,
      qualification: formData.qualification.trim() || undefined,
      skills: skillsList.length > 0 ? skillsList : undefined,
    };

    if (formData.internal_title.trim()) {
      metadata.internal_title = formData.internal_title.trim();
      updatedJD.internal_title = formData.internal_title.trim();
    }

    if (formData.business_unit.trim()) {
      metadata.business_unit = formData.business_unit.trim();
      updatedJD.business_unit = formData.business_unit.trim();
      updatedJD.division = formData.business_unit.trim();
    }

    if (formData.years_of_experience.trim()) {
      metadata.years_of_experience = formData.years_of_experience.trim();
      updatedJD.required_qualifications = {
        ...(updatedJD.required_qualifications || {}),
        experience: formatExperience(formData.years_of_experience),
      };
    }

    if (formData.qualification.trim()) {
      metadata.qualification = formData.qualification.trim();
      updatedJD.required_qualifications = {
        ...(updatedJD.required_qualifications || {}),
        education: formData.qualification.trim(),
      };
    }

    if (skillsList.length > 0) {
      metadata.skills = skillsList;
      updatedJD.required_qualifications = {
        ...(updatedJD.required_qualifications || {}),
        technical_skills: skillsList,
      };
      updatedJD.tools_technologies = skillsList;
    } else {
      delete metadata.skills;
      updatedJD.required_qualifications = {
        ...(updatedJD.required_qualifications || {}),
        technical_skills: [],
      };
      updatedJD.tools_technologies = [];
    }

    if (formData.location.trim() || formData.remote_allowed) {
      const locationParts = formData.location
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean);
      updatedJD.location = {
        ...(updatedJD.location || {}),
        ...(locationParts[0] ? { city: locationParts[0] } : {}),
        ...(locationParts.length > 1 ? { country: locationParts.slice(1).join(", ") } : {}),
        work_model: formData.remote_allowed
          ? "Remote"
          : updatedJD.location?.work_model || "Hybrid",
        travel_required: updatedJD.location?.travel_required ?? false,
      };
    }

    updatedJD.remote_allowed = formData.remote_allowed;
    metadata.dialog_inputs = {
      ...(metadata.dialog_inputs || {}),
      job_title: effectiveJobTitle || undefined,
      job_level: effectiveJobLevel,
      department: formData.department.trim() || undefined,
      years_of_experience: formData.years_of_experience.trim() || undefined,
      internal_title: formData.internal_title.trim() || undefined,
      business_unit: formData.business_unit.trim() || undefined,
      qualification: formData.qualification.trim() || undefined,
      skills: skillsList.length > 0 ? skillsList : undefined,
      location: formData.location.trim() || undefined,
      remote_allowed: formData.remote_allowed,
      user_requirements: formData.user_requirements.trim() || undefined,
    };

    updatedJD.metadata = metadata;
    return updatedJD;
  };

  const handleGenerate = async () => {
    if (generationInFlightRef.current) {
      setError("JD generation is already running. Please wait for it to finish.");
      return;
    }

    const effectiveJobTitle = getEffectiveJobTitle();
    const effectiveJobLevel = getEffectiveJobLevel();
    const missingBusinessReadyInputs = getMissingBusinessReadyInputs();

    if (missingBusinessReadyInputs.length > 0) {
      setError(
        `Cannot generate a business-ready JD. Please fill: ${missingBusinessReadyInputs.join(", ")}.`
      );
      return;
    }

    setGenerating(true);
    generationInFlightRef.current = true;
    setError(null);
    setGenerationProgress(null);
    setAgentThoughts([]);
    setGeneratedJD(null);

    try {
      const { api } = await import('@/lib/api');
      
      console.log('🔍 Starting JD Generation Request:', {
        job_title: effectiveJobTitle,
        department: formData.department,
        job_level: effectiveJobLevel,
        years_of_experience: formData.years_of_experience,
        internal_title: formData.internal_title,
        business_unit: formData.business_unit,
      });
      
      const cleanDepartment = formData.department.trim()
        .replace(/\s{2,}/g, ' ');
      
      console.log('📝 Department being sent to API:', cleanDepartment);

      const existingJobId = resolveReplaceJobId(
        replaceJobId,
        editJobId,
        editedJD?.job_id,
        editedJD?.id,
        generatedJD?.job_id,
        generatedJD?.id,
      );

      const requestPayload = {
        job_title: effectiveJobTitle,
        job_level: effectiveJobLevel,
        department: cleanDepartment,
        years_of_experience: formData.years_of_experience?.trim() || undefined,
        internal_title: formData.internal_title?.trim() || undefined,
        business_unit: formData.business_unit?.trim() || undefined,
        qualification: formData.qualification?.trim() || undefined,
        skills: formData.skills?.trim() || undefined,
        location: formData.location?.trim() || undefined,
        remote_allowed: formData.remote_allowed,
        user_requirements: formData.user_requirements?.trim() || undefined,
        ...(existingJobId ? { job_id: String(existingJobId) } : {}),
      };

      let result: JDGenerationResponse;

      try {
        setGenerationProgress("Starting AI agents (this may take 2–5 minutes)...");
        const asyncResponse = await api.jdGeneration.generateAsync(requestPayload);
        const taskId = asyncResponse.data?.task_id;
        if (!taskId) {
          throw new Error("Async JD generation did not return a task id");
        }
        result = await api.jdGeneration.pollGeneration(taskId, {
          onStatus: (status, attempt) => {
            if (status === "pending") {
              setGenerationProgress("Queued for generation...");
            } else if (status === "running") {
              setGenerationProgress(
                `Generating job description... (${Math.max(1, attempt)} checks, typically 2–5 minutes)`
              );
            }
          },
        });
      } catch (asyncError: any) {
        const status = asyncError?.response?.status;
        if (status === 404 || status === 405) {
          console.warn("Async JD generation unavailable, falling back to sync endpoint");
          setGenerationProgress("Generating job description (legacy mode, please wait)...");
          const response = await api.jdGeneration.generate(requestPayload);
          result = response.data;
        } else {
          throw asyncError;
        }
      }

      // Handle both 'jd' and 'job_description' fields for compatibility
      const jd = applyHrInputsToJD(result.job_description || result.jd || {});
      
      // CRITICAL: Preserve job_id from generation response to enable updates instead of duplicates
      const persistedJobId =
        result.postgres_job_id ||
        result.job_id ||
        existingJobId ||
        null;
      if (persistedJobId) {
        jd.job_id = persistedJobId;
        jd.id = persistedJobId;
        jd.milvus_id = persistedJobId;
        setReplaceJobId(String(persistedJobId));
        writeDraftJobId(String(persistedJobId));
        console.log(`✅ Preserved job_id from generation: ${persistedJobId}`);
      }
      if (result.milvus_id) {
        jd.milvus_id = result.milvus_id;
        console.log(`✅ Preserved milvus_id from generation: ${result.milvus_id}`);
      }
      
      // CRITICAL: Preserve ALL user inputs in generated JD
      if (jd) {
        // Preserve job title
        if (effectiveJobTitle) {
          jd.job_title = effectiveJobTitle;
          console.log(`✅ Preserved user's job title: ${jd.job_title}`);
        }
        
        // Preserve department
        if (cleanDepartment) {
          jd.department = cleanDepartment;
          console.log(`✅ Preserved user's department: ${cleanDepartment}`);
        }
        
        // Preserve location
        if (formData.location?.trim()) {
          const locationParts = formData.location.trim().split(',').map(p => p.trim());
          if (!jd.location) jd.location = {};
          jd.location.city = locationParts[0];
          jd.location.country = locationParts[1] || '';
          console.log(`✅ Preserved user's location: ${formData.location.trim()}`);
        }
        
        // Preserve remote_allowed in work_model
        if (formData.remote_allowed) {
          if (!jd.location) jd.location = {};
          jd.location.work_model = 'Remote';
          console.log(`✅ Preserved user's remote preference: Remote`);
        } else if (jd.location && !jd.location.work_model) {
          jd.location.work_model = 'Hybrid';
        }
        
        // Store job_level in metadata for reference (it's used in generation but not stored in JD structure)
        if (formData.job_level?.trim()) {
          if (!jd.metadata) jd.metadata = {};
          jd.metadata.job_level = formData.job_level.trim();
          console.log(`✅ Preserved user's job level: ${formData.job_level.trim()}`);
        }
      }
      
      if (jd) {
        if (!jd.metadata) jd.metadata = {};
        jd.metadata.job_level = effectiveJobLevel;
      }

      setGeneratedJD(jd);
      setEditedJD(jd); // Initialize edited JD with generated JD
      setHasUnsavedEdits(false);
      setAgentThoughts(result.agent_thoughts || []);
      setActiveTab("preview");
      
      // Automatically persist to pgvector if not already stored (Azure Non-Prod).
      // This ensures the JD is always available in QuantChat and Job Matching.
      if (!result.milvus_id && !result.vector_id && jd && jd.job_title && jd.department) {
        console.log('💾 Auto-saving JD to vector store (vector_id not in response)...');
        try {
          const saveResponse = await api.jdGeneration.save({
            job_id: result.job_id || jd.job_id,
            job_title: jd.job_title,
            department: jd.department,
            job_description: jd
          });
          if (saveResponse.status === 200) {
            console.log('✅ JD automatically saved to vector store:', saveResponse.data);
            // Update the JD with the saved job_id if it was generated
            if (saveResponse.data.job_id && !jd.job_id) {
              jd.job_id = saveResponse.data.job_id;
              jd.id = saveResponse.data.job_id;
              jd.milvus_id = saveResponse.data.job_id;
              setReplaceJobId(String(saveResponse.data.job_id));
              writeDraftJobId(String(saveResponse.data.job_id));
              setGeneratedJD({ ...jd });
              setEditedJD({ ...jd });
            }
          }
        } catch (saveError: any) {
          console.error('⚠️ Auto-save to vector store failed (non-critical):', saveError);
          // Don't show error to user - this is a background operation
          // The JD is still generated and can be manually saved later
        }
      } else if (result.milvus_id || result.vector_id) {
        console.log('✅ JD already stored in vector store:', result.vector_id || result.milvus_id);
      }
      
      if (onJDGenerated) {
        onJDGenerated(jd);
      }
      notifyJobsListUpdated();
    } catch (err: any) {
      console.error('❌ Error generating JD:', err);
      console.error('Error details:', {
        message: err.message,
        code: err.code,
        name: err.name,
        hasResponse: !!err.response,
        response: err.response ? {
          status: err.response.status,
          statusText: err.response.statusText,
          data: err.response.data,
          headers: err.response.headers,
        } : null,
        request: err.request ? {
          url: err.request.responseURL || err.config?.url,
          method: err.config?.method,
        } : null,
        config: err.config ? {
          url: err.config.url,
          baseURL: err.config.baseURL,
          method: err.config.method,
        } : null,
      });
      
      // Better error message handling - check response FIRST
      let errorMessage = 'Failed to generate job description. Please try again.';
      
      // If we have a response, it's NOT a network error - it's a server error
      // Check multiple ways the response might be attached
      // Network tab shows Status 500, so backend IS responding - we need to detect it properly
      const hasResponse = !!(err.response || err.status || (err.message && err.message.includes('status')));
      
      console.log('🔍 Error Classification:', {
        hasResponse,
        hasResponseObject: !!err.response,
        hasStatus: !!err.status,
        responseStatus: err.response?.status,
        errorStatus: err.status,
        errorCode: err.code,
        errorMessage: err.message,
        fullError: err,
      });
      
      if (err.response || err.status) {
        // We got a response from the server - this is a server error, not a network error
        const status = err.response?.status || err.status || 500;
        console.log('🔍 Server Error Detected:', {
          status,
          hasResponseObject: !!err.response,
          responseData: err.response?.data,
          errorStatus: err.status,
        });
        
        if (status === 500) {
          // Server error - show the actual error message from backend
          const backendError = err.response?.data?.detail || 
                             err.response?.data?.message || 
                             err.response?.data?.error?.message || 
                             err.message || 
                             'Internal server error';
          errorMessage = `Backend Error (500): ${backendError}\n\nCheck backend terminal logs for full error details.`;
        } else if (status === 404) {
          errorMessage = `Endpoint not found (404). The JD generation endpoint may not be registered. Check backend logs for "✅ JD Generation router registered successfully"`;
        } else if (status === 400) {
          errorMessage = `Bad Request (400): ${err.response?.data?.detail || err.response?.data?.message || 'Invalid request data'}`;
        } else if (status === 502 || status === 504) {
          const detail = err.response?.data?.detail || err.response?.statusText;
          const backendUrl = err.response?.data?.backend_url;
          errorMessage = detail
            ? String(detail)
            : status === 504
              ? "The request timed out while generating the job description. Try again and check API logs."
              : "Backend unavailable via BFF proxy.";
          if (backendUrl) {
            errorMessage += `\n\nBackend target: ${backendUrl}`;
          }
        } else if (err.response?.data?.detail) {
          errorMessage = err.response.data.detail;
        } else if (err.response?.data?.message) {
          errorMessage = err.response.data.message;
        } else {
          errorMessage = `Server Error (${status}): ${err.response?.statusText || err.message || 'Unknown error'}`;
        }
      } else if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
        // Timeout error - request took too long
        errorMessage = `Request Timeout: The JD generation request took longer than expected.

The AI agents may still be processing. Please:
1. Wait a moment and check the Jobs list for the generated JD
2. Check the backend terminal for completion logs
3. Try generating again if needed

Note: Complex JD generation can take 5-7 minutes.`;
      } else if (err.code === 'ECONNREFUSED' || err.code === 'ERR_NETWORK' || err.message?.includes('Network Error')) {
        errorMessage = `Connection interrupted while waiting for JD generation.

The AI agents may still be running on the server. Please:
1. Wait 1–2 minutes and refresh the Jobs list for a new draft
2. Do not click Generate again unless no job appears

If the problem persists: ${AZURE_BACKEND_HINT}`;
      } else if (err.message) {
        errorMessage = err.message;
      }
      
      setError(errorMessage);
    } finally {
      generationInFlightRef.current = false;
      setGenerating(false);
      setGenerationProgress(null);
    }
  };

  const handleSave = async () => {
    const jdToSave = editedJD || generatedJD;
    if (!jdToSave) return;

    setLoading(true);
    setError(null);
    try {
      if (!isEnterpriseFormat(jdToSave)) {
        const { api } = await import("@/lib/api");
        const titleToSave =
          formData.job_title ||
          formData.internal_title ||
          jdToSave.job_title ||
          jdToSave.title ||
          "";
        const response = await api.jobs.create({
          title: titleToSave,
          level: getEffectiveJobLevel(),
          department: formData.department,
          location: formData.location || null,
          remote_allowed: formData.remote_allowed,
          description: JSON.stringify(jdToSave),
          requirements: "",
          compensation_range: {},
        });
        if (response.status !== 201 && response.status !== 200) {
          throw new Error(response.data?.detail || "Failed to save job");
        }
        notifyJobsListUpdated();
        setHasUnsavedEdits(false);
        onOpenChange(false);
        onJDGenerated?.(jdToSave);
        return;
      }

      const prepared = prepareEnterpriseJdForSave({
        ...jdToSave,
        job_title:
          jdToSave.job_title ||
          formData.job_title ||
          formData.internal_title ||
          "",
        department: jdToSave.department || formData.department,
      });

      const result = await persistEnterpriseJdToBackend(prepared);
      const savedJd: EnterpriseJobDescription = {
        ...prepared,
        job_id: result.job_id,
        id: result.job_id,
        milvus_id: result.job_id,
      };

      setReplaceJobId(String(result.job_id));
      writeDraftJobId(String(result.job_id));

      setGeneratedJD(savedJd);
      setEditedJD(savedJd);
      setHasUnsavedEdits(false);
      notifyJobsListUpdated();

      writeDraftJobId(null);
      onOpenChange(false);
      onJDGenerated?.(savedJd);
    } catch (err: any) {
      console.error("❌ Error saving JD:", err);
      const errorMessage =
        err.response?.data?.detail || err.message || "Failed to save job. Please try again.";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const getAgentIcon = (agent: string) => {
    if (agent.includes("Generator")) return "🎯";
    if (agent.includes("Refiner")) return "✨";
    if (agent.includes("Validator")) return "✅";
    if (agent.includes("RAG")) return "🔍";
    if (agent.includes("Storage")) return "💾";
    return "🤖";
  };

  const getPhaseColor = (phase: string) => {
    switch (phase) {
      case "OBSERVE": return "bg-blue-100 text-blue-800";
      case "THINK": return "bg-purple-100 text-purple-800";
      case "PLAN": return "bg-yellow-100 text-yellow-800";
      case "ACT": return "bg-green-100 text-green-800";
      case "REFLECT": return "bg-orange-100 text-orange-800";
      default: return "bg-gray-100 text-gray-800";
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleDialogOpenChange}>
      <DialogContent className="sm:max-w-[1040px] max-h-[90vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            {isEditMode ? JD_DIALOG_TITLE_EDIT : JD_DIALOG_TITLE_CREATE}
            {backendConnected === false && (
              <span className="ml-2 text-xs text-red-500 flex items-center gap-1">
                <AlertCircle className="h-4 w-4" />
                Backend Offline
              </span>
            )}
            {backendConnected === true && (
              <span className="ml-2 text-xs text-green-500 flex items-center gap-1">
                <CheckCircle2 className="h-4 w-4" />
                Connected
              </span>
            )}
          </DialogTitle>
          <DialogDescription>
            {isEditMode ? JD_DIALOG_DESC_EDIT : JD_DIALOG_DESC_CREATE}
            {backendConnected === false && (
              <span className="block mt-2 text-red-600 text-sm font-medium">
                {connectionMessage || "Cannot connect to backend via BFF."} {AZURE_BACKEND_HINT}
              </span>
            )}
          </DialogDescription>
        </DialogHeader>

        {loadingExisting ? (
          <div className="flex flex-1 items-center justify-center py-16">
            <div className="text-center space-y-3">
              <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">Loading saved job description...</p>
            </div>
          </div>
        ) : (
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex-1 flex flex-col overflow-hidden">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="form">{isEditMode ? "HR Inputs" : "Job Details"}</TabsTrigger>
            <TabsTrigger value="preview" disabled={!generatedJD}>
              {isEditMode ? "Job Description" : "Generated JD"}{" "}
              {generatedJD && <CheckCircle2 className="ml-2 h-4 w-4 text-green-500" />}
            </TabsTrigger>
            <TabsTrigger value="thoughts" disabled={agentThoughts.length === 0}>
              Agent Thoughts ({agentThoughts.length})
            </TabsTrigger>
          </TabsList>

          <TabsContent value="form" className="flex-1 overflow-auto">
            <form className="space-y-5 py-4">
              <section className="rounded-md border bg-background p-4">
                <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
                  <Briefcase className="h-4 w-4 text-primary" />
                  Role Details
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="job_title">Public JD Title</Label>
                    <Input
                      id="job_title"
                      placeholder="Optional; defaults to Internal Title"
                      value={formData.job_title}
                      onChange={(e) => setFormData({ ...formData, job_title: e.target.value })}
                    />
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="derived_job_level">Derived Seniority</Label>
                    <div
                      id="derived_job_level"
                      className="flex h-10 items-center rounded-md border bg-muted/30 px-3"
                    >
                      <Badge variant="secondary">{getDisplayedJobLevel()}</Badge>
                    </div>
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="department">Department *</Label>
                    <Input
                      id="department"
                      placeholder="e.g., Application Development"
                      value={formData.department}
                      onChange={(e) => {
                        let deptValue = e.target.value;
                        deptValue = deptValue.replace(/\s{2,}/g, ' ');
                        setFormData({ ...formData, department: deptValue });
                      }}
                      onBlur={(e) => {
                        let deptValue = e.target.value.trim();
                        deptValue = deptValue.replace(/\s{2,}/g, ' ');
                        if (deptValue !== formData.department) {
                          setFormData({ ...formData, department: deptValue });
                        }
                      }}
                      required
                    />
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="location">Location</Label>
                    <Input
                      id="location"
                      placeholder="e.g., Bengaluru, Pune, Remote"
                      value={formData.location}
                      onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                    />
                  </div>
                </div>
              </section>

              <section className="rounded-md border bg-background p-4">
                <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
                  <Building2 className="h-4 w-4 text-primary" />
                  HR Matrix
                </div>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="grid gap-2">
                    <Label htmlFor="internal_title">Internal Title *</Label>
                    <Input
                      id="internal_title"
                      placeholder="e.g., Senior Consultant L1"
                      value={formData.internal_title}
                      onChange={(e) => setFormData({ ...formData, internal_title: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="years_of_experience">Years of Exp *</Label>
                    <Input
                      id="years_of_experience"
                      placeholder="e.g., 5-7"
                      value={formData.years_of_experience}
                      onChange={(e) => setFormData({ ...formData, years_of_experience: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="business_unit">Business Unit (BU)</Label>
                    <Input
                      id="business_unit"
                      placeholder="e.g., Cloud & Infrastructure Services (CIS)"
                      value={formData.business_unit}
                      onChange={(e) => setFormData({ ...formData, business_unit: e.target.value })}
                    />
                  </div>
                </div>

                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="qualification" className="flex items-center gap-2">
                      <GraduationCap className="h-4 w-4 text-muted-foreground" />
                      Qualification *
                    </Label>
                    <Textarea
                      id="qualification"
                      placeholder="e.g., B.E / B.Tech / MCA"
                      rows={3}
                      value={formData.qualification}
                      onChange={(e) => setFormData({ ...formData, qualification: e.target.value })}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="skills">Skills *</Label>
                    <Textarea
                      id="skills"
                      placeholder="e.g., Java, .NET, Spring Boot, REST APIs, Agile"
                      rows={3}
                      value={formData.skills}
                      onChange={(e) => setFormData({ ...formData, skills: e.target.value })}
                    />
                  </div>
                </div>
              </section>

              <section className="rounded-md border bg-background p-4">
                <div className="mb-4 flex items-center gap-2 text-sm font-semibold">
                  <SlidersHorizontal className="h-4 w-4 text-primary" />
                  Work Model & Notes
                </div>
                <div className="space-y-4">
                  <div className="flex items-center space-x-2 rounded-md border bg-muted/20 px-3 py-2">
                    <Checkbox
                      id="remote_allowed"
                      checked={formData.remote_allowed}
                      onCheckedChange={(checked) =>
                        setFormData({ ...formData, remote_allowed: checked as boolean })
                      }
                    />
                    <Label htmlFor="remote_allowed" className="cursor-pointer">
                      Remote work allowed
                    </Label>
                  </div>

                  <div className="grid gap-2">
                    <Label htmlFor="user_requirements">Additional Requirements</Label>
                    <Textarea
                      id="user_requirements"
                      placeholder="Any specific requirements, skills, or preferences..."
                      rows={4}
                      value={formData.user_requirements}
                      onChange={(e) => setFormData({ ...formData, user_requirements: e.target.value })}
                    />
                  </div>
                </div>
              </section>

              {generationProgress && generating && (
                <div className="flex items-center gap-2 rounded-md border border-blue-200 bg-blue-50 p-3">
                  <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
                  <span className="text-sm text-blue-800">{generationProgress}</span>
                </div>
              )}

              {error && (
                <div className="flex items-center gap-2 rounded-md border border-red-200 bg-red-50 p-3">
                  <AlertCircle className="h-4 w-4 text-red-600" />
                  <span className="text-sm text-red-600">{error}</span>
                </div>
              )}
            </form>
          </TabsContent>

          <TabsContent value="preview" className="flex-1 overflow-auto">
            {generatedJD ? (
              <ScrollArea className="h-full">
                <div className="py-4">
                  {hasUnsavedEdits && (
                    <div className="mb-4 flex items-center gap-2 rounded-md border border-amber-200 bg-amber-50 p-3">
                      <AlertCircle className="h-4 w-4 text-amber-700" />
                      <span className="text-sm text-amber-800">
                        {JD_UNSAVED_BANNER}
                      </span>
                    </div>
                  )}
                  <JDPreviewCard
                    jd={editedJD || generatedJD || {}}
                    jobDetails={{
                      department: formData.department,
                      location: formData.location,
                      remote_allowed: formData.remote_allowed,
                      job_level: getEffectiveJobLevel(),
                      years_of_experience: formData.years_of_experience,
                      internal_title: formData.internal_title,
                      business_unit: formData.business_unit,
                      qualification: formData.qualification,
                      skills: formData.skills,
                    }}
                    onUpdate={(updatedJD) => {
                      setEditedJD(updatedJD);
                      setFormData((prev) => ({
                        ...buildJdGenerationFormFromJob(
                          {
                            title: updatedJD.job_title,
                            department: updatedJD.department,
                            level: updatedJD.metadata?.job_level,
                            location: updatedJD.location?.city,
                            remote_allowed:
                              updatedJD.location?.work_model === "Remote",
                          },
                          updatedJD
                        ),
                        user_requirements: prev.user_requirements,
                      }));
                    }}
                    onUnsavedChange={setHasUnsavedEdits}
                    onPersisted={(savedJD) => {
                      setEditedJD(savedJD);
                      setGeneratedJD(savedJD);
                      setReplaceJobId(
                        resolveReplaceJobId(savedJD.job_id, savedJD.id, replaceJobId, editJobId)
                      );
                      setHasUnsavedEdits(false);
                      notifyJobsListUpdated();
                      onJDGenerated?.(savedJD);
                    }}
                    onSave={handleSave}
                    isEditable={true}
                  />
                </div>
              </ScrollArea>
            ) : (
              <div className="flex items-center justify-center h-64">
                <p className="text-muted-foreground">No JD generated yet. Click "Generate JD" to start.</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="thoughts" className="flex-1 overflow-auto">
            <ScrollArea className="h-full">
              <div className="space-y-4 py-4">
                <div className="p-4 bg-blue-50 border border-blue-200 rounded-md">
                  <h3 className="font-semibold text-blue-800 mb-2">🤖 Autonomous Agent Thinking Process</h3>
                  <p className="text-sm text-blue-700">
                    Watch how agents observe, think, plan, act, and reflect autonomously.
                  </p>
                </div>

                {agentThoughts.length > 0 ? (
                  <div className="space-y-3">
                    {agentThoughts.map((thought, idx) => (
                      <div
                        key={idx}
                        className="p-4 border rounded-lg bg-card hover:bg-accent/50 transition-colors"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-2xl">{getAgentIcon(thought.agent)}</span>
                            <span className="font-semibold">{thought.agent}</span>
                            {thought.autonomous && (
                              <Badge variant="outline" className="text-xs">Autonomous</Badge>
                            )}
                          </div>
                          {thought.state && (
                            <Badge className={getPhaseColor(thought.state)}>{thought.state}</Badge>
                          )}
                        </div>

                        <p className="text-sm mb-2">{thought.thought}</p>

                        {thought.action && (
                          <div className="mt-2 pt-2 border-t">
                            <p className="text-xs text-muted-foreground">
                              <strong>Action:</strong> {thought.action}
                            </p>
                          </div>
                        )}

                        {thought.reasoning && (
                          <details className="mt-2">
                            <summary className="text-xs text-muted-foreground cursor-pointer">
                              View Reasoning
                            </summary>
                            <div className="mt-2 p-2 bg-muted rounded text-xs">
                              <pre className="whitespace-pre-wrap">
                                {JSON.stringify(thought.reasoning, null, 2)}
                              </pre>
                            </div>
                          </details>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-64">
                    <p className="text-muted-foreground">
                      Agent thoughts will appear here during generation...
                    </p>
                  </div>
                )}
              </div>
            </ScrollArea>
          </TabsContent>
        </Tabs>
        )}

        <DialogFooter className="flex-shrink-0">
          <Button type="button" variant="outline" onClick={requestDialogClose}>
            Cancel
          </Button>
          
          {/* Regenerate button - shown when JD exists */}
          {generatedJD && (
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                if (!window.confirm(JD_REGENERATE_CONFIRM)) {
                  return;
                }
                setReplaceJobId((current) =>
                  resolveReplaceJobId(
                    current,
                    editJobId,
                    editedJD?.job_id,
                    editedJD?.id,
                    generatedJD?.job_id,
                    generatedJD?.id,
                  )
                );
                setGeneratedJD(null);
                setEditedJD(null);
                setHasUnsavedEdits(false);
                setError(null);
                setActiveTab("form");
                setDialogMode("create");
              }}
            >
              <Sparkles className="mr-2 h-4 w-4" />
              {JD_REGENERATE_BUTTON_LABEL}
            </Button>
          )}
          
          {!generatedJD && (
            <Button
              type="button"
              onClick={handleGenerate}
              disabled={
                generating ||
                backendConnected === false ||
                getMissingBusinessReadyInputs().length > 0
              }
            >
              {generating ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Generating with AI Agents...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-4 w-4" />
                  Generate JD
                </>
              )}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
