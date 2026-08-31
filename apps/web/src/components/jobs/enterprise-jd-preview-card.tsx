"use client";

import { useState, useEffect, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { 
  MapPin, Building2, Briefcase, Edit2, Save, X, CheckCircle2, Code, Users, Gift,
  GraduationCap, Star, Download, Loader2, ChevronDown, ChevronUp,
  Target, Heart, Send, Building, Pencil, Plus, Trash2, FileText
} from "lucide-react";
import { MalomatiaTemplateDialog } from "@/components/jobs/malomatia-template-dialog";
import type { EnterpriseJobDescription, LocationModel, WorkEnvironment, ApplicationInstructions, RequiredQualifications, CustomJDSection } from "@/types/enterprise-jd";
import {
  formatApplicationInstructions,
  formatDepartmentTeam,
  formatLocation,
  formatWorkEnvironmentLines,
  getDepartmentSectionLabel,
  isLocationToBeConfirmed,
  ENTERPRISE_JD_SECTIONS,
  buildVisibleSectionNumberMap,
  getCustomSectionNumber,
  formatNumberedSectionLabel,
} from "@/types/enterprise-jd";
import {
  formatJdSaveSuccessMessage,
  JD_EDIT_MODE_HINT,
  JD_SAVE_BUTTON_LABEL,
  JD_SAVE_FOOTER_HINT,
} from "@/lib/jd-hr-copy";
import {
  notifyJobsListUpdated,
  persistEnterpriseJdToBackend,
  prepareEnterpriseJdForSave,
  resolveJdDocumentId,
  serializeJdSnapshot,
} from "@/lib/jd-persist";

interface EnterpriseJDPreviewCardProps {
  jd: EnterpriseJobDescription;
  onSave?: (updatedJD: EnterpriseJobDescription) => void;
  onUpdate?: (updatedJD: EnterpriseJobDescription) => void;
  onPersisted?: (updatedJD: EnterpriseJobDescription) => void;
  onUnsavedChange?: (hasUnsavedChanges: boolean) => void;
  isEditable?: boolean;
}

export function EnterpriseJDPreviewCard({ 
  jd, 
  onSave, 
  onUpdate,
  onPersisted,
  onUnsavedChange,
  isEditable = true 
}: EnterpriseJDPreviewCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedJD, setEditedJD] = useState<EnterpriseJobDescription>(jd);
  const [isDownloading, setIsDownloading] = useState(false);
  const [malomatiaDialogOpen, setMalomatiaDialogOpen] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({});
  const persistedSnapshotRef = useRef<string>(serializeJdSnapshot(jd));
  const persistedDocumentIdRef = useRef<string | null>(resolveJdDocumentId(jd));

  const syncPersistedSnapshot = (nextJd: EnterpriseJobDescription) => {
    persistedSnapshotRef.current = serializeJdSnapshot(nextJd);
    persistedDocumentIdRef.current = resolveJdDocumentId(nextJd);
    onUnsavedChange?.(false);
  };

  const reportUnsavedState = (candidate: EnterpriseJobDescription) => {
    const dirty = serializeJdSnapshot(candidate) !== persistedSnapshotRef.current;
    onUnsavedChange?.(dirty);
    return dirty;
  };

  // Sync editedJD when jd prop changes (but only when not editing).
  // Only reset the persisted baseline when the vector document id changes (new generation).
  useEffect(() => {
    if (!isEditing) {
      const clonedJD = JSON.parse(JSON.stringify(jd)) as EnterpriseJobDescription;
      if (jd.job_id && !clonedJD.job_id) {
        clonedJD.job_id = jd.job_id;
      }
      if (jd.id && !clonedJD.id && !clonedJD.job_id) {
        clonedJD.job_id = jd.id;
      }
      setEditedJD(clonedJD);

      const documentId = resolveJdDocumentId(clonedJD);
      if (documentId !== persistedDocumentIdRef.current) {
        syncPersistedSnapshot(clonedJD);
      } else {
        reportUnsavedState(clonedJD);
      }
    }
  }, [jd, isEditing]);

  useEffect(() => {
    reportUnsavedState(editedJD);
  }, [editedJD]);

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const handleEdit = () => {
    setEditedJD(JSON.parse(JSON.stringify(jd))); // Deep clone
    setIsEditing(true);
    setSaveMessage(null);
  };

  const handleCancel = () => {
    const resetJd = JSON.parse(JSON.stringify(jd)) as EnterpriseJobDescription;
    setEditedJD(resetJd);
    setIsEditing(false);
    reportUnsavedState(resetJd);
  };

  const handleSaveEdit = () => {
    void handleSaveToDatabase();
  };

  const handleSaveToDatabase = async () => {
    setIsSaving(true);
    setSaveMessage(null);

    if (isEditing) {
      onUpdate?.(editedJD);
      setIsEditing(false);
    }

    const jdToSave = prepareEnterpriseJdForSave(editedJD);
    const existingJobId =
      jdToSave.job_id || jdToSave.id || jd.job_id || jd.id || null;

    try {
      const result = await persistEnterpriseJdToBackend(jdToSave);
      const savedJobId = result.job_id;
      const savedJd: EnterpriseJobDescription = {
        ...jdToSave,
        job_id: savedJobId,
        id: savedJobId,
        milvus_id: savedJobId,
      };

      setEditedJD(savedJd);
      syncPersistedSnapshot(savedJd);
      onUpdate?.(savedJd);
      onPersisted?.(savedJd);
      notifyJobsListUpdated();

      setSaveMessage(
        formatJdSaveSuccessMessage({
          jobTitle: savedJd.job_title,
          jobId: savedJobId,
          updated: Boolean(existingJobId),
        })
      );
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "Connection failed";
      setSaveMessage(`❌ Error: ${errorMessage}`);
      console.error("❌ Save exception:", error);
    } finally {
      setIsSaving(false);
    }
  };

  const currentJD = editedJD;
  const sectionLabel = (sectionId: string, title: string) =>
    formatNumberedSectionLabel(currentJD, sectionId, title);
  const departmentSectionLabel = getDepartmentSectionLabel(currentJD);
  const departmentDisplay = formatDepartmentTeam(currentJD, { labeled: true });
  const locationPending = isLocationToBeConfirmed(currentJD.location);
  const headerLocation = locationPending
    ? "Location to be confirmed"
    : [
        currentJD.location?.city,
        currentJD.location?.country,
      ].filter((part) => typeof part === "string" && part.trim()).join(", ");
  const travelPercentage = Number(currentJD.location?.travel_percentage || 0);

  const getRemovedSections = (source: EnterpriseJobDescription = editedJD) =>
    source.metadata?.removed_sections || [];

  const isSectionVisible = (sectionId: string, source: EnterpriseJobDescription = currentJD) =>
    !getRemovedSections(source).includes(sectionId);

  const CONTENT_SECTION_IDS = [
    "about_company",
    "position_summary",
    "responsibilities",
    "required_qualifications",
    "preferred_qualifications",
    "soft_skills",
    "tools_technologies",
    "success_metrics",
    "work_environment",
    "compensation_benefits",
    "equal_opportunity_statement",
    "application_instructions",
  ] as const;

  const hasVisibleContentSectionBefore = (
    sectionId: string,
    source: EnterpriseJobDescription = currentJD
  ) => {
    const index = CONTENT_SECTION_IDS.indexOf(
      sectionId as (typeof CONTENT_SECTION_IDS)[number]
    );
    if (index <= 0) return false;
    return CONTENT_SECTION_IDS.slice(0, index).some((id) => isSectionVisible(id, source));
  };

  const contentSectionClass = (
    sectionId: string,
    source: EnterpriseJobDescription = currentJD
  ) => {
    if (!isSectionVisible(sectionId, source)) return "hidden";
    return hasVisibleContentSectionBefore(sectionId, source) ? "border-t pt-4 mt-2" : "";
  };

  const customSectionClass = (index: number) => {
    const hasPriorStandard = CONTENT_SECTION_IDS.some((id) => isSectionVisible(id));
    return hasPriorStandard || index > 0 ? "border-t pt-4 mt-2" : "pt-2";
  };

  const setSectionVisibility = (sectionId: string, visible: boolean) => {
    setEditedJD(prev => {
      const removed = prev.metadata?.removed_sections || [];
      const nextRemoved = visible
        ? removed.filter(id => id !== sectionId)
        : Array.from(new Set([...removed, sectionId]));
      return {
        ...prev,
        metadata: {
          ...(prev.metadata || {}),
          removed_sections: nextRemoved,
        },
      };
    });
  };

  const addCustomSection = () => {
    const newSection: CustomJDSection = {
      id: `custom-${Date.now()}`,
      title: "New Section",
      content: "",
    };
    setEditedJD(prev => ({
      ...prev,
      custom_sections: [...(prev.custom_sections || []), newSection],
    }));
  };

  const updateCustomSection = (sectionId: string, patch: Partial<CustomJDSection>) => {
    setEditedJD(prev => ({
      ...prev,
      custom_sections: (prev.custom_sections || []).map(section =>
        section.id === sectionId ? { ...section, ...patch } : section
      ),
    }));
  };

  const removeCustomSection = (sectionId: string) => {
    setEditedJD(prev => ({
      ...prev,
      custom_sections: (prev.custom_sections || []).filter(section => section.id !== sectionId),
    }));
  };

  // Helper functions for updating nested objects
  const updateField = <K extends keyof EnterpriseJobDescription>(field: K, value: EnterpriseJobDescription[K]) => {
    setEditedJD(prev => ({ ...prev, [field]: value }));
  };

  const updateLocation = (field: keyof LocationModel, value: LocationModel[keyof LocationModel]) => {
    setEditedJD(prev => ({ ...prev, location: { ...prev.location, [field]: value } }));
  };

  const updateWorkEnv = (field: keyof WorkEnvironment, value: WorkEnvironment[keyof WorkEnvironment]) => {
    setEditedJD(prev => ({ ...prev, work_environment: { ...prev.work_environment, [field]: value } }));
  };

  const updateAppInstructions = (field: keyof ApplicationInstructions, value: ApplicationInstructions[keyof ApplicationInstructions]) => {
    setEditedJD(prev => ({ ...prev, application_instructions: { ...prev.application_instructions, [field]: value } }));
  };

  const updateReqQual = (field: keyof RequiredQualifications, value: RequiredQualifications[keyof RequiredQualifications]) => {
    setEditedJD(prev => ({ ...prev, required_qualifications: { ...prev.required_qualifications, [field]: value } }));
  };

  // Helper to update metadata fields (like job_level)
  const updateMetadata = (field: string, value: string | null) => {
    setEditedJD(prev => ({ 
      ...prev, 
      metadata: { 
        ...(prev.metadata || {}), 
        [field]: value 
      } 
    }));
  };

  // Parse helpers - allow ALL characters in input, only split on delimiter
  // Use newline for array fields to allow commas within items
  const parseNewlineList = (v: string): string[] => v.split('\n');
  const joinNewline = (arr: string[]): string => (arr || []).join('\n');
  // For display only (comma-separated display)
  const joinForDisplay = (arr: string[]): string => (arr || []).join(', ');

  // Tech term corrections - fix common spacing issues in technology names
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

  // Helper: Normalize tech terms by fixing common spacing issues
  const normalizeTechTerms = (text: string): string => {
    if (!text) return text;
    let result = text;
    for (const [incorrect, correct] of Object.entries(TECH_TERM_CORRECTIONS)) {
      result = result.split(incorrect).join(correct);
    }
    return result;
  };

  // Helper: Add spaces between concatenated words (e.g., "EdgePlatformEngineer" → "Edge Platform Engineer")
  const addSpacesToConcatenatedWords = (text: string): string => {
    if (!text) return text;
    
    let cleaned = String(text);

    // Preserve short HR/band codes such as A1, A2, B3, C1 exactly.
    if (/^[A-Z]{1,3}\d{1,3}$/i.test(cleaned.trim())) {
      return cleaned.trim();
    }
    
    // Step 1: Fix CamelCase/PascalCase words (e.g., "EdgePlatformEngineer" → "Edge Platform Engineer")
    // Pattern: lowercase or digit followed by uppercase letter
    cleaned = cleaned.replace(/([a-z0-9])([A-Z])/g, '$1 $2');
    
    // Step 2: Fix all-caps words followed by lowercase (e.g., "AWSIoT" → "AWS IoT")
    // Pattern: 2+ uppercase letters followed by lowercase
    cleaned = cleaned.replace(/([A-Z]{2,})([a-z])/g, '$1 $2');
    
    // Step 3: Fix common concatenated patterns
    // - "IoT" patterns: "IoTDevice" → "IoT Device"
    cleaned = cleaned.replace(/(IoT)([A-Z])/g, '$1 $2');
    // - "API" patterns: "APIDesign" → "API Design"
    cleaned = cleaned.replace(/(API)([A-Z])/g, '$1 $2');
    // - "AWS", "GCP", "Azure" patterns
    cleaned = cleaned.replace(/(AWS|GCP|Azure)([A-Z])/g, '$1 $2');
    // - "CI/CD" patterns
    cleaned = cleaned.replace(/(CI\/CD)([A-Z])/g, '$1 $2');
    
    // Step 4: Fix common word boundaries that might be concatenated
    // - Numbers followed by words: "5years" → "5 years"
    cleaned = cleaned.replace(/(\d+)([A-Za-z])/g, '$1 $2');
    // - Words followed by numbers: "years5" → "years 5" (less common, but handle it)
    cleaned = cleaned.replace(/([A-Za-z])(\d+)/g, '$1 $2');
    cleaned = cleaned.replace(/\b([A-Z])\s+(\d{1,3})\b/g, '$1$2');
    
    // Step 5: Normalize multiple spaces
    cleaned = cleaned.replace(/ {2,}/g, ' ');
    
    return cleaned.trim();
  };

  // Helper: Check if text looks garbled (needs cleaning)
  // Returns true if text appears to have garbled characters (spaces/ampersands between single chars)
  const looksGarbled = (text: string): boolean => {
    if (!text || text.length < 2) return false;
    
    // Check for patterns that indicate garbled text:
    // 1. Ampersands between alphanumeric characters: "D&o&c"
    if (/([a-zA-Z0-9])&+([a-zA-Z0-9])/.test(text)) return true;
    
    // 2. Many single-character words separated by spaces: "D o c u m e n t"
    const parts = text.split(/\s+/);
    const singleCharParts = parts.filter(p => p.length === 1 && /[a-zA-Z0-9]/.test(p));
    // If more than 30% of parts are single characters, it's likely garbled
    if (parts.length > 3 && singleCharParts.length / parts.length > 0.3) return true;
    
    // 3. Corrupted separators: "!" or "!'" patterns
    if (/!\s*['"]?\s*&?\s*/.test(text) || /&\s*!\s*/.test(text)) return true;
    
    // 4. If text has many spaces but short words, might be garbled
    if (parts.length > 5 && parts.every(p => p.length <= 2)) return true;
    
    return false;
  };

  // Helper: Clean garbled text (spaces/ampersands between characters)
  // Only fixes garbled text (single chars separated by spaces), preserves normal words
  const cleanGarbledText = (text: string): string => {
    if (!text) return text;
    
    let cleaned = String(text);
    
    // Step 0: Fix corrupted separators FIRST (before processing words)
    // Fix "!'" patterns that should be " / " or just " /"
    cleaned = cleaned.replace(/!\s*['"]?\s*/g, ' / ');
    cleaned = cleaned.replace(/!\s*&/g, ' / ');
    cleaned = cleaned.replace(/&!\s*/g, ' / ');
    
    // Step 1: Remove ampersands between alphanumeric characters: "D&o&c" → "Doc"
    cleaned = cleaned.replace(/([a-zA-Z0-9])&+([a-zA-Z0-9])/g, '$1$2');
    
    // Step 2: Fix concatenated words (missing spaces) - do this before fixing garbled text
    cleaned = addSpacesToConcatenatedWords(cleaned);
    
    // Step 3: Fix garbled text - spaces between single characters
    // Split by spaces and reconstruct intelligently
    const parts = cleaned.split(/\s+/);
    const reconstructed: string[] = [];
    let i = 0;
    
    while (i < parts.length) {
      const part = parts[i];
      
      // Skip empty parts
      if (!part) {
        i++;
        continue;
      }
      
      // If it's a separator like "/", convert arrow to slash, preserve separators
      if (part === '/' || part === '|') {
        reconstructed.push(part);
        i++;
        continue;
      }
      
      // Convert unicode arrow to plain slash
      if (part === '→' || part === '->' || part === '=>') {
        reconstructed.push('/');
        i++;
        continue;
      }
      
      // If it's a single alphanumeric character, check if next parts are also single chars
      if (part.length === 1 && /[a-zA-Z0-9]/.test(part)) {
        const wordChars: string[] = [part];
        i++;
        
        // Collect consecutive single-character alphanumeric parts
        while (i < parts.length) {
          const nextPart = parts[i];
          
          // Stop if we hit a separator
          if (nextPart === '/' || nextPart === '→' || nextPart === '|') {
            break;
          }
          
          // If it's a single alphanumeric char, add it to the word
          if (nextPart.length === 1 && /[a-zA-Z0-9]/.test(nextPart)) {
            wordChars.push(nextPart);
            i++;
          } else if (nextPart.length > 1) {
            // Hit a normal word, stop collecting
            break;
          } else {
            // Some other character, skip it
            i++;
          }
        }
        
        // If we collected multiple chars, join them into a word
        if (wordChars.length > 1) {
          reconstructed.push(wordChars.join(''));
        } else {
          // Single char - might be part of an acronym or just a single letter word
          reconstructed.push(wordChars[0]);
        }
      } else {
        // Normal word (length > 1) or special character - preserve it
        reconstructed.push(part);
        i++;
      }
    }
    
    // Rejoin with spaces, but preserve separators
    cleaned = reconstructed.join(' ');
    
    // Step 4: Normalize converted separators without changing normal HR-entered slash text.
    // Preserve inputs like "L1/Delivery Lead L1" and "B.E/ B.Tech/MBA" exactly.
    cleaned = cleaned.replace(/\s*→\s*/g, ' / ');
    cleaned = cleaned.replace(/\s*->\s*/g, ' / ');
    cleaned = cleaned.replace(/\s*=>\s*/g, ' / ');
    
    // Step 5: Handle remaining problematic patterns
    cleaned = cleaned.replace(/\s*!\s*['"]?\s*/g, ' / ');
    cleaned = cleaned.replace(/\s*&\s*!\s*/g, ' / ');
    
    // Step 6: Clean up multiple spaces and normalize
    cleaned = cleaned.replace(/ {2,}/g, ' ');
    cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
    
    // Step 7: Trim and clean up any trailing separators
    cleaned = cleaned.trim();
    cleaned = cleaned.replace(/^\s*\/\s*|\s*\/\s*$/g, ''); // Remove leading/trailing slashes
    
    // Step 8: Normalize tech terms (fix spacing issues like "Num Py" -> "NumPy")
    cleaned = normalizeTechTerms(cleaned);
    
    return cleaned.trim();
  };

  // PDF Generation - Clean Professional Format (No Colors)
  // IMPORTANT: Always use editedJD which is kept in sync with jd via useEffect
  // This ensures user edits are always reflected in PDF
  const handleDownloadPDF = async () => {
    console.log('📄 PDF Download button clicked');
    setIsDownloading(true);
    try {
      // Use editedJD which always has the latest data:
      // - When editing: contains user's edits
      // - When not editing: synced with jd prop via useEffect
      const jdToUse = editedJD;
      console.log('📄 JD data to use:', jdToUse?.job_title);
      
      console.log('📄 Loading jsPDF library...');
      const { jsPDF } = await import('jspdf');
      console.log('📄 jsPDF loaded successfully');
      
      const doc = new jsPDF();
      const pageWidth = doc.internal.pageSize.getWidth();
      const margin = 20;
      const contentWidth = pageWidth - (margin * 2);
      let yPos = 20;
      const pageBottom = 270;
      const ensureSpace = (height: number) => {
        if (yPos + height > pageBottom) {
          doc.addPage();
          yPos = 20;
        }
      };

      // Helper: Add text with word wrap
      const addText = (text: string, fontSize: number, isBold = false) => {
        // Ensure text is a string, normalize it, and clean garbled text
        let normalizedText = String(text || '').trim();
        if (!normalizedText) return;
        
        // Clean garbled text (spaces/ampersands between characters)
        normalizedText = cleanGarbledText(normalizedText);
        
        doc.setFontSize(fontSize);
        doc.setFont("helvetica", isBold ? "bold" : "normal");
        doc.setTextColor(0, 0, 0);
        const lines = doc.splitTextToSize(normalizedText, contentWidth);
        
        // Ensure lines is an array and render each line properly
        if (Array.isArray(lines) && lines.length > 0) {
          ensureSpace(lines.length * ((fontSize * 0.4) + 2));
          lines.forEach((line: string) => {
            doc.text(line, margin, yPos);
            yPos += (fontSize * 0.4) + 2;
            if (yPos > pageBottom) { doc.addPage(); yPos = 20; }
          });
        } else {
          // Fallback: render as single line
          ensureSpace((fontSize * 0.4) + 4);
          doc.text(normalizedText, margin, yPos);
          yPos += (fontSize * 0.4) + 4;
        }
        
        if (yPos > pageBottom) { doc.addPage(); yPos = 20; }
      };

      // Helper: Add section header (clean, no background color)
      const addHeader = (num: number, title: string) => {
        ensureSpace(22);
        yPos += 6;
        doc.setFontSize(11);
        doc.setFont("helvetica", "bold");
        doc.setTextColor(0, 0, 0);
        doc.text(`${num}. ${title}`, margin, yPos);
        // Add underline
        doc.setDrawColor(0, 0, 0);
        doc.setLineWidth(0.5);
        doc.line(margin, yPos + 2, margin + contentWidth, yPos + 2);
        yPos += 8;
      };

      // Helper: Add bullet points
      const addBullets = (items: string[]) => {
        doc.setFontSize(10);
        doc.setFont("helvetica", "normal");
        doc.setTextColor(40, 40, 40);
        items.forEach(item => {
          let normalizedItem = String(item || '').trim();
          if (!normalizedItem) return;
          
          // Clean garbled text (spaces/ampersands between characters)
          normalizedItem = cleanGarbledText(normalizedItem);
          
          const bulletText = `• ${normalizedItem}`;
          const lines = doc.splitTextToSize(bulletText, contentWidth - 8);
          
          // Render each line properly
          if (Array.isArray(lines) && lines.length > 0) {
            ensureSpace(lines.length * 6);
            lines.forEach((line: string) => {
              doc.text(line, margin + 5, yPos);
              yPos += 4 + 2;
              if (yPos > pageBottom) { doc.addPage(); yPos = 20; }
            });
          } else {
            ensureSpace(6);
            doc.text(bulletText, margin + 5, yPos);
            yPos += 4 + 2;
          }
          
          if (yPos > pageBottom) { doc.addPage(); yPos = 20; }
        });
      };

      // Title Header (Clean - Black text, no background)
      // Clean concatenated words in job title
      doc.setFontSize(20);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(0, 0, 0);
      const cleanedTitle = cleanGarbledText(jdToUse.job_title || "Job Description");
      doc.text(cleanedTitle, margin, yPos);
      yPos += 8;
      
      // Subtitle: Department, Location & Level
      // Clean concatenated words in department and location
      doc.setFontSize(11);
      doc.setFont("helvetica", "normal");
      doc.setTextColor(80, 80, 80);
      // CRITICAL: For department, check if it looks like garbled text before cleaning
      // User-edited text should be preserved as-is unless it's clearly garbled
      const deptRaw = String(formatDepartmentTeam(jdToUse) || '').trim();
      const cleanedDept = deptRaw && looksGarbled(deptRaw) ? cleanGarbledText(deptRaw) : deptRaw;
      const formattedLocation = formatLocation(jdToUse.location);
      const jobLevelRaw = jdToUse.metadata?.job_level || '';
      const cleanedJobLevel = jobLevelRaw ? cleanGarbledText(jobLevelRaw) : '';
      const subtitleParts = [
        cleanedDept,
        formattedLocation
      ].filter(Boolean);
      if (cleanedJobLevel) {
        subtitleParts.splice(1, 0, cleanedJobLevel); // Insert level after department
      }
      const subtitle = subtitleParts.join(' | ');
      doc.text(subtitle, margin, yPos);
      yPos += 10;
      
      // Horizontal line separator
      doc.setDrawColor(0, 0, 0);
      doc.setLineWidth(1);
      doc.line(margin, yPos, margin + contentWidth, yPos);
      yPos += 10;

      const pdfSectionNumbers = buildVisibleSectionNumberMap(jdToUse);
      const pdfHeader = (sectionId: string, title: string) => {
        const num = pdfSectionNumbers.get(sectionId);
        if (num != null) {
          addHeader(num, title);
        }
      };

      // Visible sections only — numbering is contiguous after HITL removals
      if (isSectionVisible("job_title", jdToUse)) {
      pdfHeader("job_title", "Job Title"); 
      // Clean concatenated words in job title
      doc.setFontSize(10);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(0, 0, 0);
      const cleanedJobTitle = cleanGarbledText(jdToUse.job_title || '');
      const jobLevelSuffix = cleanedJobLevel ? ` (${cleanedJobLevel})` : '';
      const jobTitleWithLevel = cleanedJobTitle + jobLevelSuffix;
      const jobTitleLines = doc.splitTextToSize(jobTitleWithLevel, contentWidth);
      if (Array.isArray(jobTitleLines) && jobTitleLines.length > 0) {
        ensureSpace(jobTitleLines.length * 6);
        jobTitleLines.forEach((line: string) => {
          doc.text(line, margin, yPos);
          yPos += 4 + 2;
          if (yPos > pageBottom) { doc.addPage(); yPos = 20; }
        });
      } else {
        ensureSpace(6);
        doc.text(jobTitleWithLevel, margin, yPos);
        yPos += 4 + 2;
      }
      }
      
      if (isSectionVisible("department_team", jdToUse)) {
      pdfHeader("department_team", getDepartmentSectionLabel(jdToUse)); 
      // Clean concatenated words in department/team/division
      // CRITICAL: Preserve user-edited text unless it's clearly garbled
      let dept = String(jdToUse.department || '').trim();
      
      // Only apply aggressive cleaning if text looks garbled
      if (dept && looksGarbled(dept)) {
        // First, try to detect if it contains garbled separators and fix them
        dept = dept.replace(/!\s*['"]?\s*&?\s*/g, ' / ');
        dept = dept.replace(/&\s*!\s*/g, ' / ');
        // Now clean the garbled text
        dept = cleanGarbledText(dept);
        // If department contains " / ", split, clean each part, and rejoin
        if (dept.includes(' / ')) {
          const deptParts = dept.split(/\s*\/\s*/).map(part => {
            const trimmed = part.trim();
            return looksGarbled(trimmed) ? cleanGarbledText(trimmed) : trimmed;
          }).filter(Boolean);
          dept = deptParts.join(' / ');
        }
      } else if (dept) {
        // For normal text, only apply minimal cleaning (fix obvious concatenation issues)
        dept = addSpacesToConcatenatedWords(dept);
      }
      
      const deptTeamRaw = formatDepartmentTeam(
        { ...jdToUse, department: dept },
        { labeled: true }
      );
      const deptTeam = looksGarbled(deptTeamRaw) ? cleanGarbledText(deptTeamRaw) : deptTeamRaw;
      doc.setFontSize(10);
      doc.setFont("helvetica", "normal");
      doc.setTextColor(0, 0, 0);
      const deptLines = doc.splitTextToSize(deptTeam, contentWidth);
      if (Array.isArray(deptLines) && deptLines.length > 0) {
        ensureSpace(deptLines.length * 6);
        deptLines.forEach((line: string) => {
          doc.text(line, margin, yPos);
          yPos += 4 + 2;
          if (yPos > pageBottom) { doc.addPage(); yPos = 20; }
        });
      } else {
        ensureSpace(6);
        doc.text(deptTeam, margin, yPos);
        yPos += 4 + 2;
      }
      }
      
      if (isSectionVisible("location_work_model", jdToUse)) {
      pdfHeader("location_work_model", "Location & Work Model"); 
      addText(formatLocation(jdToUse.location), 10);
      }
      
      if (isSectionVisible("about_company", jdToUse)) {
        pdfHeader("about_company", "About the Company");
        addText(jdToUse.about_company, 10);
      }

      if (isSectionVisible("position_summary", jdToUse)) {
        pdfHeader("position_summary", "Position Summary");
        addText(jdToUse.position_summary, 10);
      }

      if (isSectionVisible("responsibilities", jdToUse)) {
        pdfHeader("responsibilities", "Key Responsibilities");
        addBullets(jdToUse.responsibilities || []);
      }

      if (isSectionVisible("required_qualifications", jdToUse)) {
        pdfHeader("required_qualifications", "Required Qualifications");
        const cleanedEducation = cleanGarbledText(jdToUse.required_qualifications?.education || '');
        const cleanedExperience = cleanGarbledText(jdToUse.required_qualifications?.experience || '');
        const cleanedTechSkills = (jdToUse.required_qualifications?.technical_skills || []).map(s => cleanGarbledText(s)).join(", ");
        addText(`Qualification: ${cleanedEducation}`, 10);
        addText(`Experience: ${cleanedExperience}`, 10);
        addText(`Skills: ${cleanedTechSkills}`, 10);
      }

      if (isSectionVisible("preferred_qualifications", jdToUse)) {
        pdfHeader("preferred_qualifications", "Preferred Qualifications");
        addBullets(jdToUse.preferred_qualifications || []);
      }

      if (isSectionVisible("soft_skills", jdToUse)) {
        pdfHeader("soft_skills", "Core Competencies / Soft Skills");
        addBullets(jdToUse.soft_skills || []);
      }

      if (isSectionVisible("tools_technologies", jdToUse)) {
        pdfHeader("tools_technologies", "Skills & Technologies");
        const cleanedTools = (jdToUse.tools_technologies || []).map(t => cleanGarbledText(t)).join(", ");
        addText(cleanedTools, 10);
      }

      if (isSectionVisible("success_metrics", jdToUse)) {
        pdfHeader("success_metrics", "Success Metrics / KPIs");
        addBullets(jdToUse.success_metrics || []);
      }

      if (isSectionVisible("work_environment", jdToUse)) {
        pdfHeader("work_environment", "Work Environment");
        formatWorkEnvironmentLines(jdToUse.work_environment).forEach((line) => addText(line, 10));
      }

      if (isSectionVisible("compensation_benefits", jdToUse)) {
        pdfHeader("compensation_benefits", "Compensation & Benefits");
        addBullets(jdToUse.compensation_benefits || []);
      }

      if (isSectionVisible("equal_opportunity_statement", jdToUse)) {
        pdfHeader("equal_opportunity_statement", "Equal Opportunity Statement");
        addText(jdToUse.equal_opportunity_statement, 9);
      }

      if (isSectionVisible("application_instructions", jdToUse)) {
        pdfHeader("application_instructions", "Application Instructions");
        addText(formatApplicationInstructions(jdToUse.application_instructions), 10);
      }

      (jdToUse.custom_sections || []).forEach((section, index) => {
        if (!section.title && !section.content) return;
        addHeader(getCustomSectionNumber(jdToUse, index), section.title || `Custom Section ${index + 1}`);
        addText(section.content, 10);
      });

      // Footer on all pages
      const pageCount = doc.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.setTextColor(120, 120, 120);
        doc.text(`Generated by QuantHire AI | Page ${i} of ${pageCount}`, pageWidth / 2, 287, { align: 'center' });
      }

      const fileName = `${cleanGarbledText(jdToUse.job_title || 'Job_Description').replace(/\s+/g, '_')}_JD.pdf`;
      console.log('📄 Saving PDF as:', fileName);
      doc.save(fileName);
      console.log('📄 PDF saved successfully!');
    } catch (error) {
      console.error('❌ PDF Generation Error:', error);
      alert(`PDF generation failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsDownloading(false);
    }
  };


  return (
    <Card className="w-full border-2 border-green-200 bg-gradient-to-br from-white to-green-50/30">
      {/* HEADER - Section 1, 2, 3 */}
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex-1 space-y-2">
            {/* Section 1: Job Title + Job Level */}
            <div className={isSectionVisible("job_title") ? "" : "hidden"}>
            {isEditing ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <div>
                  <Label className="text-xs text-muted-foreground">1a. Job Title *</Label>
                  <Input value={editedJD.job_title} onChange={(e) => updateField('job_title', e.target.value)} className="text-xl font-bold" placeholder="Job Title" />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">1b. Job Level</Label>
                  <Input 
                    value={editedJD.metadata?.job_level || ''} 
                    onChange={(e) => updateMetadata('job_level', e.target.value || null)} 
                    placeholder="e.g., Senior, Mid-level, Junior, Lead, Principal"
                    list="job-levels"
                  />
                  <datalist id="job-levels">
                    <option value="Junior" />
                    <option value="Mid-level" />
                    <option value="Senior" />
                    <option value="Lead" />
                    <option value="Principal" />
                    <option value="Staff" />
                    <option value="Manager" />
                    <option value="Director" />
                    <option value="VP" />
                    <option value="C-Level" />
                  </datalist>
                </div>
              </div>
            ) : (
              <CardTitle className="text-xl flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                {currentJD.job_title}
                {currentJD.metadata?.job_level && (
                  <Badge variant="secondary" className="ml-2 text-xs bg-blue-100 text-blue-800">
                    {currentJD.metadata.job_level}
                  </Badge>
                )}
                <Badge variant="outline" className="ml-2 text-xs">Enterprise Format</Badge>
              </CardTitle>
            )}
            </div>
            
            {/* Section 2: Department / Team / Division */}
            <div className={isSectionVisible("department_team") ? "" : "hidden"}>
            {isEditing ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <div>
                  <Label className="text-xs text-muted-foreground">2a. Department / Grade *</Label>
                  <Input value={editedJD.department} onChange={(e) => updateField('department', e.target.value)} placeholder="Department" />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">2b. Team</Label>
                  <Input value={editedJD.team || ''} onChange={(e) => updateField('team', e.target.value || null)} placeholder="Team (optional)" />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">2c. Division</Label>
                  <Input value={editedJD.division || ''} onChange={(e) => updateField('division', e.target.value || null)} placeholder="Division (optional)" />
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-1 text-sm text-muted-foreground">
                <Building2 className="h-4 w-4" />
                <span className="font-medium text-foreground/80">{departmentSectionLabel}:</span>
                <span>{departmentDisplay}</span>
              </div>
            )}
            </div>

            {/* Section 3: Location & Work Model */}
            <div className={isSectionVisible("location_work_model") ? "" : "hidden"}>
            {isEditing ? (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-2">
                <div>
                  <Label className="text-xs text-muted-foreground">3a. City</Label>
                  <Input value={editedJD.location.city} onChange={(e) => updateLocation('city', e.target.value)} placeholder="City" />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">3b. Country</Label>
                  <Input value={editedJD.location.country} onChange={(e) => updateLocation('country', e.target.value)} placeholder="Country" />
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">3c. Work Model</Label>
                  <Input 
                    value={editedJD.location.work_model} 
                    onChange={(e) => updateLocation('work_model', e.target.value as 'On-site' | 'Hybrid' | 'Remote')} 
                    placeholder="Work Model"
                    list="work-models"
                  />
                  <datalist id="work-models">
                    <option value="On-site" />
                    <option value="Hybrid" />
                    <option value="Remote" />
                  </datalist>
                </div>
                <div>
                  <Label className="text-xs text-muted-foreground">3d. Travel %</Label>
                  <Input type="number" min="0" max="100" value={editedJD.location.travel_percentage || ''} onChange={(e) => updateLocation('travel_percentage', e.target.value ? parseInt(e.target.value) : null)} placeholder="0-100" />
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
                {currentJD.metadata?.job_level && (
                  <span className="flex items-center gap-1">
                    <Briefcase className="h-4 w-4" />
                    {currentJD.metadata.job_level}
                  </span>
                )}
                {headerLocation && (
                  <span className="flex items-center gap-1"><MapPin className="h-4 w-4" />{headerLocation}</span>
                )}
                {!locationPending && (
                  <Badge variant="outline" className="text-green-600 border-green-300">{currentJD.location.work_model}</Badge>
                )}
                {travelPercentage > 0 && <span>Travel: {travelPercentage}%</span>}
              </div>
            )}
            </div>
          </div>
          
          {/* Edit/Save Buttons */}
          {isEditable && !isEditing && (
            <Button variant="outline" size="sm" onClick={handleEdit} className="ml-4">
              <Pencil className="h-4 w-4 mr-1" />Edit All Sections
            </Button>
          )}
          {isEditing && (
            <div className="flex gap-2 ml-4">
              <Button variant="outline" size="sm" onClick={handleCancel}><X className="h-4 w-4 mr-1" />Cancel</Button>
              <Button
                size="sm"
                onClick={handleSaveEdit}
                disabled={isSaving}
                className="bg-green-600 hover:bg-green-700"
              >
                {isSaving ? (
                  <><Loader2 className="h-4 w-4 mr-1 animate-spin" />Saving...</>
                ) : (
                  <><Save className="h-4 w-4 mr-1" />{JD_SAVE_BUTTON_LABEL}</>
                )}
              </Button>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {isEditing && (
          <div className="rounded-lg border bg-muted/20 p-4 space-y-4">
            <div>
              <Label className="text-sm font-semibold">JD Sections</Label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-3">
                {ENTERPRISE_JD_SECTIONS.map((section) => (
                  <label key={section.id} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={isSectionVisible(section.id, editedJD)}
                      onCheckedChange={(checked) => setSectionVisibility(section.id, checked === true)}
                    />
                    <span>{formatNumberedSectionLabel(editedJD, section.id, section.label)}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="space-y-3 border-t pt-3">
              <div className="flex items-center justify-between gap-2">
                <Label className="text-sm font-semibold">Custom Sections</Label>
                <Button type="button" variant="outline" size="sm" onClick={addCustomSection}>
                  <Plus className="h-4 w-4 mr-1" />
                  Add Section
                </Button>
              </div>

              {(editedJD.custom_sections || []).map((section) => (
                <div key={section.id} className="rounded-md border bg-background p-3 space-y-2">
                  <div className="flex gap-2">
                    <Input
                      value={section.title}
                      onChange={(e) => updateCustomSection(section.id, { title: e.target.value })}
                      placeholder="Section title"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => removeCustomSection(section.id)}
                      title="Remove section"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  <Textarea
                    value={section.content}
                    onChange={(e) => updateCustomSection(section.id, { content: e.target.value })}
                    rows={4}
                    placeholder="Section content"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Section 4: About the Company */}
        <div className={contentSectionClass("about_company")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Building className="h-4 w-4 text-blue-500" />{sectionLabel("about_company", "About the Company")}
          </Label>
          {isEditing ? (
            <Textarea value={editedJD.about_company} onChange={(e) => updateField('about_company', e.target.value)} rows={3} placeholder="Company description (2-3 sentences about mission, scale, industry)" />
          ) : (
            <p className="text-sm text-muted-foreground">{currentJD.about_company}</p>
          )}
        </div>

        {/* Section 5: Position Summary */}
        <div className={contentSectionClass("position_summary")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Star className="h-4 w-4 text-yellow-500" />{sectionLabel("position_summary", "Position Summary")}
          </Label>
          {isEditing ? (
            <Textarea value={editedJD.position_summary} onChange={(e) => updateField('position_summary', e.target.value)} rows={4} placeholder="Role purpose, impact, collaboration (3-5 sentences)" />
          ) : (
            <p className="text-sm text-muted-foreground">{currentJD.position_summary}</p>
          )}
        </div>

        {/* Section 6: Key Responsibilities */}
        <div className={contentSectionClass("responsibilities")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Briefcase className="h-4 w-4 text-orange-500" />{sectionLabel("responsibilities", "Key Responsibilities (8-15 items)")}
          </Label>
          {isEditing ? (
            <Textarea 
              value={joinNewline(editedJD.responsibilities)} 
              onChange={(e) => updateField('responsibilities', e.target.value.split('\n'))} 
              rows={10} 
              placeholder="One responsibility per line (start with action verbs)" 
            />
          ) : (
            <>
              <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                {(expandedSections['resp'] ? currentJD.responsibilities : currentJD.responsibilities.slice(0, 5)).map((r, i) => <li key={i}>{r}</li>)}
              </ul>
              {currentJD.responsibilities.length > 5 && (
                <Button variant="ghost" size="sm" onClick={() => toggleSection('resp')} className="mt-1 text-xs">
                  {expandedSections['resp'] ? <><ChevronUp className="h-3 w-3 mr-1" />Show less</> : <><ChevronDown className="h-3 w-3 mr-1" />Show {currentJD.responsibilities.length - 5} more</>}
                </Button>
              )}
            </>
          )}
        </div>


        {/* Section 7: Required Qualifications */}
        <div className={contentSectionClass("required_qualifications")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <GraduationCap className="h-4 w-4 text-green-500" />{sectionLabel("required_qualifications", "Required Qualifications")}
          </Label>
          {isEditing ? (
            <div className="space-y-2">
              <div>
                <Label className="text-xs text-muted-foreground">7a. Qualification</Label>
                <Input value={editedJD.required_qualifications.education} onChange={(e) => updateReqQual('education', e.target.value)} placeholder="Qualification requirement" />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">7b. Experience (include years)</Label>
                <Input value={editedJD.required_qualifications.experience} onChange={(e) => updateReqQual('experience', e.target.value)} placeholder="e.g., 5+ years of experience in..." />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">7c. Skills (one per line)</Label>
                <Textarea value={joinNewline(editedJD.required_qualifications.technical_skills)} onChange={(e) => updateReqQual('technical_skills', parseNewlineList(e.target.value))} rows={4} placeholder="One skill per line, e.g.:\nPython\nTensorFlow\nAWS\nDocker" />
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground space-y-1">
              <p><strong>Qualification:</strong> {currentJD.required_qualifications.education}</p>
              <p><strong>Experience:</strong> {currentJD.required_qualifications.experience}</p>
              <p><strong>Skills:</strong> {currentJD.required_qualifications.technical_skills.join(", ")}</p>
            </div>
          )}
        </div>

        {/* Section 8: Preferred Qualifications */}
        <div className={contentSectionClass("preferred_qualifications")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Star className="h-4 w-4 text-purple-500" />{sectionLabel("preferred_qualifications", "Preferred Qualifications (3-8 items)")}
          </Label>
          {isEditing ? (
            <Textarea value={joinNewline(editedJD.preferred_qualifications)} onChange={(e) => updateField('preferred_qualifications', parseNewlineList(e.target.value))} rows={5} placeholder="One qualification per line" />
          ) : (
            <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
              {currentJD.preferred_qualifications.map((q, i) => <li key={i}>{q}</li>)}
            </ul>
          )}
        </div>

        {/* Section 9: Soft Skills */}
        <div className={contentSectionClass("soft_skills")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Users className="h-4 w-4 text-purple-500" />{sectionLabel("soft_skills", "Core Competencies / Soft Skills (4-10 items)")}
          </Label>
          {isEditing ? (
            <Textarea value={joinNewline(editedJD.soft_skills)} onChange={(e) => updateField('soft_skills', parseNewlineList(e.target.value))} rows={5} placeholder="One skill per line" />
          ) : (
            <div className="flex flex-wrap gap-2">
              {currentJD.soft_skills.map((s, i) => <Badge key={i} variant="outline" className="border-purple-300 text-purple-700">{s}</Badge>)}
            </div>
          )}
        </div>

        {/* Section 10: Skills & Technologies */}
        <div className={contentSectionClass("tools_technologies")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Code className="h-4 w-4 text-blue-500" />{sectionLabel("tools_technologies", "Skills & Technologies")}
          </Label>
          {isEditing ? (
            <Textarea value={joinNewline(editedJD.tools_technologies)} onChange={(e) => updateField('tools_technologies', parseNewlineList(e.target.value))} rows={4} placeholder="One skill or technology per line, e.g.:\nSolution Architecture\nAPI Architecture\nDelivery Management\nRisk Management" />
          ) : (
            <div className="flex flex-wrap gap-2">
              {currentJD.tools_technologies.map((t, i) => <Badge key={i} variant="secondary" className="bg-blue-100 text-blue-800">{t}</Badge>)}
            </div>
          )}
        </div>

        {/* Section 11: Success Metrics */}
        <div className={contentSectionClass("success_metrics")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Target className="h-4 w-4 text-red-500" />{sectionLabel("success_metrics", "Success Metrics / KPIs (3-8 items)")}
          </Label>
          {isEditing ? (
            <Textarea value={joinNewline(editedJD.success_metrics)} onChange={(e) => updateField('success_metrics', parseNewlineList(e.target.value))} rows={5} placeholder="One metric per line" />
          ) : (
            <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
              {currentJD.success_metrics.map((m, i) => <li key={i}>{m}</li>)}
            </ul>
          )}
        </div>

        {/* Section 12: Work Environment */}
        <div className={contentSectionClass("work_environment")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Building2 className="h-4 w-4 text-gray-500" />{sectionLabel("work_environment", "Work Environment / Reporting Structure")}
          </Label>
          {isEditing ? (
            <div className="grid grid-cols-2 gap-2">
              <div>
                <Label className="text-xs text-muted-foreground">12a. Reports To</Label>
                <Input value={editedJD.work_environment.reports_to} onChange={(e) => updateWorkEnv('reports_to', e.target.value)} placeholder="Manager title" />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">12b. Team Size</Label>
                <Input type="number" min="1" value={editedJD.work_environment.team_size || ''} onChange={(e) => updateWorkEnv('team_size', e.target.value ? parseInt(e.target.value) : null)} placeholder="e.g., 8" />
              </div>
              <div className="col-span-2">
                <Label className="text-xs text-muted-foreground">12c. Collaborates With (one per line)</Label>
                <Textarea value={joinNewline(editedJD.work_environment.collaborates_with)} onChange={(e) => updateWorkEnv('collaborates_with', parseNewlineList(e.target.value))} rows={3} placeholder="One team per line, e.g.:\nProduct Management\nUX Design\nDevOps" />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">12d. Collaboration Mode</Label>
                <Input value={editedJD.work_environment.collaboration_mode || ''} onChange={(e) => updateWorkEnv('collaboration_mode', e.target.value || null)} placeholder="e.g., Agile, Scrum" />
              </div>
            </div>
          ) : (
            <div className="text-sm text-muted-foreground space-y-1">
              {formatWorkEnvironmentLines(currentJD.work_environment).map((line, index) => (
                <p key={index}>{line}</p>
              ))}
            </div>
          )}
        </div>

        {/* Section 13: Compensation & Benefits */}
        <div className={contentSectionClass("compensation_benefits")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Gift className="h-4 w-4 text-pink-500" />{sectionLabel("compensation_benefits", "Compensation & Benefits")}
          </Label>
          {isEditing ? (
            <Textarea value={joinNewline(editedJD.compensation_benefits)} onChange={(e) => updateField('compensation_benefits', parseNewlineList(e.target.value))} rows={6} placeholder="One benefit per line (include salary range if applicable)" />
          ) : (
            <>
              <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                {(expandedSections['benefits'] ? currentJD.compensation_benefits : currentJD.compensation_benefits.slice(0, 4)).map((b, i) => <li key={i}>{b}</li>)}
              </ul>
              {currentJD.compensation_benefits.length > 4 && (
                <Button variant="ghost" size="sm" onClick={() => toggleSection('benefits')} className="mt-1 text-xs">
                  {expandedSections['benefits'] ? <><ChevronUp className="h-3 w-3 mr-1" />Show less</> : <><ChevronDown className="h-3 w-3 mr-1" />Show more</>}
                </Button>
              )}
            </>
          )}
        </div>

        {/* Section 14: Equal Opportunity Statement */}
        <div className={contentSectionClass("equal_opportunity_statement")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Heart className="h-4 w-4 text-red-500" />{sectionLabel("equal_opportunity_statement", "Equal Opportunity Statement")}
          </Label>
          {isEditing ? (
            <Textarea value={editedJD.equal_opportunity_statement} onChange={(e) => updateField('equal_opportunity_statement', e.target.value)} rows={3} placeholder="EEO statement about diversity and inclusion" />
          ) : (
            <p className="text-xs text-muted-foreground">{currentJD.equal_opportunity_statement}</p>
          )}
        </div>

        {/* Section 15: Application Instructions */}
        <div className={contentSectionClass("application_instructions")}>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Send className="h-4 w-4 text-green-500" />{sectionLabel("application_instructions", "Application Instructions")}
          </Label>
          {isEditing ? (
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label className="text-xs text-muted-foreground">15a. Apply URL</Label>
                <Input value={editedJD.application_instructions.apply_url || ''} onChange={(e) => updateAppInstructions('apply_url', e.target.value || null)} placeholder="https://..." />
              </div>
              <div>
                <Label className="text-xs text-muted-foreground">15b. Email</Label>
                <Input value={editedJD.application_instructions.email || ''} onChange={(e) => updateAppInstructions('email', e.target.value || null)} placeholder="careers@company.com" />
              </div>
              <div className="col-span-3">
                <Label className="text-xs text-muted-foreground">15c. Required Materials (one per line)</Label>
                <Textarea value={joinNewline(editedJD.application_instructions.required_materials)} onChange={(e) => updateAppInstructions('required_materials', parseNewlineList(e.target.value))} rows={3} placeholder="One material per line, e.g.:\nResume\nCover Letter\nPortfolio" />
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">{formatApplicationInstructions(currentJD.application_instructions)}</p>
          )}
        </div>

        {!isEditing && (currentJD.custom_sections || []).map((section, index) => (
          <div key={section.id} className={customSectionClass(index)}>
            <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
              <Star className="h-4 w-4 text-yellow-500" />
              {getCustomSectionNumber(currentJD, index)}. {section.title || "Custom Section"}
            </Label>
            <p className="text-sm text-muted-foreground whitespace-pre-wrap">
              {section.content}
            </p>
          </div>
        ))}
      </CardContent>


      {/* FOOTER - Actions */}
      <CardFooter className="border-t bg-muted/30 pt-4 flex flex-col gap-3">
        {/* Status Message */}
        {saveMessage && (
          <div className={`w-full p-3 rounded-md text-sm font-medium ${saveMessage.startsWith('✅') ? 'bg-green-100 text-green-800 border border-green-300' : 'bg-red-100 text-red-800 border border-red-300'}`}>
            {saveMessage}
          </div>
        )}
        
        {/* Edit Mode Indicator */}
        {isEditing && (
          <div className="w-full p-2 bg-yellow-50 border border-yellow-200 rounded-md text-sm text-yellow-800 flex items-center gap-2">
            <Edit2 className="h-4 w-4" />
            <span>{JD_EDIT_MODE_HINT}</span>
          </div>
        )}
        
        {/* Action Buttons */}
        <div className="flex gap-2 w-full">
          <Button variant="outline" className="flex-1" onClick={handleDownloadPDF} disabled={isDownloading}>
            {isDownloading ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Generating PDF...</>
            ) : (
              <><Download className="h-4 w-4 mr-2" />Download as PDF</>
            )}
          </Button>
          <Button
            variant="outline"
            className="flex-1"
            onClick={() => setMalomatiaDialogOpen(true)}
            disabled={isEditing}
            title={isEditing ? "Finish editing before exporting to Malomatia template" : undefined}
          >
            <FileText className="h-4 w-4 mr-2" />
            Convert to Malomatia Template
          </Button>
        </div>
        <MalomatiaTemplateDialog
          open={malomatiaDialogOpen}
          onOpenChange={setMalomatiaDialogOpen}
          jd={editedJD}
        />
        
        {/* Persist JD (footer — disabled while inline edit uses header Save) */}
        <Button
          className="w-full bg-blue-600 hover:bg-blue-700 text-white"
          onClick={handleSaveToDatabase}
          disabled={isSaving || isEditing}
          title={isEditing ? "Use Save job description in the header while editing" : undefined}
        >
          {isSaving ? (
            <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Saving...</>
          ) : (
            <><Save className="h-4 w-4 mr-2" />{JD_SAVE_BUTTON_LABEL}</>
          )}
        </Button>
        
        <p className="text-xs text-muted-foreground text-center">
          {isEditing
            ? "Finish editing using Save job description above."
            : JD_SAVE_FOOTER_HINT}
        </p>
      </CardFooter>
    </Card>
  );
}
