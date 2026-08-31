"use client";

import React, { useState, useCallback, useEffect } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Loader2, X } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { AZURE_BACKEND_HINT, AZURE_RESUME_HINT } from '@/lib/azure-messages';

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024;
const UPLOAD_TIMEOUT_MS = 620_000;

interface UploadResult {
  success: boolean;
  resume_id?: string;
  message?: string;
  parsed_data?: any;
  screening_report?: any;
  pdf_extraction_method?: string;
  raw_blob_ref?: string;
  processed_blob_ref?: string;
  error?: string;
}

interface ResumeUploadProps {
  onUploadSuccess?: () => void;
}

async function parseUploadError(response: Response): Promise<string> {
  const raw = await response.text();
  try {
    const payload = JSON.parse(raw) as { detail?: unknown; backend_url?: string };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      let message = payload.detail;
      if (payload.backend_url) {
        message += `\n\nBackend target: ${payload.backend_url}`;
      }
      return message;
    }
  } catch {
    // fall through to raw text
  }
  if (response.status === 502) {
    return `Backend unavailable via BFF. ${AZURE_BACKEND_HINT}`;
  }
  if (response.status === 504) {
    return `Upload timed out while parsing the resume. Document Intelligence and AI extraction can take several minutes. ${AZURE_RESUME_HINT}`;
  }
  return raw || `Server error: HTTP ${response.status}`;
}

export const ResumeUpload: React.FC<ResumeUploadProps> = ({ onUploadSuccess }) => {
  const [file, setFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResult | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [notification, setNotification] = useState<{type: 'success' | 'error' | 'info', message: string} | null>(null);
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null);
  const [connectionMessage, setConnectionMessage] = useState<string | null>(null);

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const { checkBackendHealth, testResumeParsingReady } = await import('@/lib/api-health');
        await checkBackendHealth();
        const resumeReady = await testResumeParsingReady();
        setBackendConnected(resumeReady.success);
        setConnectionMessage(resumeReady.success ? null : resumeReady.message);
      } catch (error) {
        setBackendConnected(false);
        setConnectionMessage(
          error instanceof Error ? error.message : 'Unable to verify resume parsing readiness'
        );
      }
    };
    void checkConnection();
  }, []);

  const showNotification = useCallback((type: 'success' | 'error' | 'info', message: string) => {
    setNotification({ type, message });
    setTimeout(() => setNotification(null), 5000); // Auto-hide after 5 seconds
  }, []);

  const handleFileSelect = useCallback((selectedFile: File) => {
    console.log('File selected:', selectedFile.name, selectedFile.type);
    const name = selectedFile.name.toLowerCase();
    const allowed =
      selectedFile.type === 'text/plain' ||
      selectedFile.type === 'application/pdf' ||
      selectedFile.type === 'application/msword' ||
      selectedFile.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
      selectedFile.type.startsWith('image/') ||
      ['.txt', '.pdf', '.doc', '.docx', '.png', '.jpg', '.jpeg', '.webp', '.tif', '.tiff', '.bmp'].some(
        (ext) => name.endsWith(ext)
      );

    if (selectedFile && allowed) {
      if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
        const errorMsg = 'File exceeds the 10 MB upload limit.';
        setUploadResult({ success: false, error: errorMsg });
        showNotification('error', errorMsg);
        return;
      }
      setFile(selectedFile);
      setUploadResult(null);
      showNotification('success', `${selectedFile.name} is ready for upload.`);
    } else {
      const errorMsg =
        'Please select a resume: PDF, DOCX, DOC, TXT, or image (PNG/JPG/WEBP/TIFF)';
      setUploadResult({
        success: false,
        error: errorMsg
      });
      showNotification('error', errorMsg);
    }
  }, [showNotification]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  }, [handleFileSelect]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  }, [handleFileSelect]);

  const uploadResume = async () => {
    if (!file) {
      showNotification('error', 'Please select a resume file to upload.');
      return;
    }
    if (backendConnected === false) {
      showNotification('error', connectionMessage || `Resume parsing is unavailable. ${AZURE_RESUME_HINT}`);
      return;
    }

    setIsUploading(true);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);
      
      const { apiFetch } = await import("@/lib/api-client");
      const response = await apiFetch("/v1/resume-parsing/upload-resume", {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(await parseUploadError(response));
      }

      const result = await response.json();

      if (result.success) {
        setUploadResult({
          success: true,
          resume_id: result.resume_id,
          message: result.message,
          parsed_data: result.parsed_data,
          screening_report: result.screening_report || result.parsed_data?.screening_report,
          pdf_extraction_method: result.pdf_extraction_method,
          raw_blob_ref: result.raw_blob_ref,
          processed_blob_ref: result.processed_blob_ref,
        });
        setFile(null);
        showNotification('success', result.message || "Resume uploaded and parsed successfully.");
        
        if (onUploadSuccess) {
          onUploadSuccess();
        }
      } else {
        const errorMsg = result.error || result.message || 'Upload failed';
        setUploadResult({ success: false, error: errorMsg });
        showNotification('error', errorMsg);
      }
    } catch (error) {
      let errorMessage = 'Failed to upload resume. Please try again.';
      
      if (error instanceof Error) {
        if (error.name === 'AbortError') {
          errorMessage = `Upload timed out after ${Math.round(UPLOAD_TIMEOUT_MS / 60000)} minutes. ${AZURE_RESUME_HINT}`;
        } else {
          errorMessage = error.message;
        }
      }
      
      setUploadResult({ success: false, error: errorMessage });
      showNotification('error', errorMessage);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Upload Resume
          {backendConnected === false && (
            <span className="ml-2 text-xs text-red-500 flex items-center gap-1">
              <AlertCircle className="h-4 w-4" />
              Parser Offline
            </span>
          )}
          {backendConnected === true && (
            <span className="ml-2 text-xs text-green-500 flex items-center gap-1">
              <CheckCircle className="h-4 w-4" />
              Ready
            </span>
          )}
        </CardTitle>
        {backendConnected === false && connectionMessage && (
          <p className="text-sm text-red-600">{connectionMessage}. {AZURE_RESUME_HINT}</p>
        )}
      </CardHeader>
      <CardContent className="space-y-6">
        {/* File Upload Area */}
        <div
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-all duration-200 cursor-pointer ${
            dragActive
              ? 'border-brand-teal bg-brand-teal/10 scale-105'
              : file
              ? 'border-brand-teal bg-brand-teal/15'
              : 'border-brand-gray/60 hover:border-brand-gray hover:bg-brand-light/60'
          }`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => {
            if (!file) {
              document.getElementById('file-input')?.click();
            }
          }}
        >
          {file ? (
            <div className="space-y-2">
              <CheckCircle className="h-12 w-12 text-brand-teal mx-auto" />
              <p className="text-lg font-medium text-brand-teal">{file.name}</p>
              <p className="text-sm text-brand-dark/70">
                {(file.size / 1024).toFixed(1)} KB
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  setFile(null);
                  setUploadResult(null);
                }}
                className="mt-2"
              >
                <X className="h-4 w-4 mr-1" />
                Remove File
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              <Upload className="h-12 w-12 text-brand-gray mx-auto" />
              <div>
                <p className="text-lg font-medium text-brand-dark">
                  {dragActive ? (
                    <span className="text-brand-teal">Drop your resume here!</span>
                  ) : (
                    <>
                      Drop your resume here, or{' '}
                      <span className="text-brand-teal hover:text-brand-teal/80">click to browse</span>
                    </>
                  )}
                </p>
                <Input
                  id="file-input"
                  type="file"
                  accept=".txt,.pdf,.doc,.docx,.png,.jpg,.jpeg,.webp,.tif,.tiff,.bmp"
                  onChange={handleFileInput}
                  className="hidden"
                />
                <p className="text-sm text-brand-dark/60 mt-2">
                  Supports PDF, Word (DOC/DOCX), TXT, and scanned images (max 10 MB)
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Upload Button */}
        <div className="flex justify-center">
          <Button
            onClick={uploadResume}
            disabled={!file || isUploading || backendConnected === false}
            className="w-full max-w-xs"
          >
            {isUploading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Extracting &amp; parsing resume...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4 mr-2" />
                Upload Resume
              </>
            )}
          </Button>
        </div>

        {/* Upload Result */}
        {uploadResult && (
          <div className={`p-4 rounded-lg ${
            uploadResult.success
              ? 'bg-brand-teal/10 border border-brand-teal/40'
              : 'bg-brand-red/10 border border-brand-red/40'
          }`}>
            <div className="flex items-start gap-3">
              {uploadResult.success ? (
                <CheckCircle className="h-5 w-5 text-brand-teal mt-0.5" />
              ) : (
                <AlertCircle className="h-5 w-5 text-brand-red mt-0.5" />
              )}
              <div className="flex-1">
                <p className={`font-medium ${
                  uploadResult.success ? 'text-brand-teal' : 'text-brand-red'
                }`}>
                  {uploadResult.success ? 'Upload Successful!' : 'Upload Failed'}
                </p>
                <p className={`text-sm mt-1 ${
                  uploadResult.success ? 'text-brand-teal/80' : 'text-brand-red/80'
                }`}>
                  {uploadResult.success ? uploadResult.message : uploadResult.error}
                </p>
                
                {uploadResult.success && uploadResult.parsed_data && (
                  <div className="mt-3 space-y-2">
                    <p className="text-sm font-medium text-brand-teal">Parsed Information:</p>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div>
                        <span className="font-medium">Name:</span> {(() => {
                          const name = uploadResult.parsed_data.personal_info?.name || 
                                       uploadResult.parsed_data.name || 
                                       "";
                          // Filter out filename-like patterns (contains "resume", "–", or " - " in the middle)
                          if (name && (
                            name.toLowerCase().includes('resume') || 
                            name.includes(' – ') || 
                            name.includes(' - ') ||
                            name.endsWith(' – Resume') ||
                            name.endsWith(' - Resume')
                          )) {
                            // Try to extract actual name (before the pattern)
                            const cleaned = name.split(/[–-]/)[0].trim();
                            return cleaned || "Not available";
                          }
                          return name || "Not available";
                        })()}
                      </div>
                      <div>
                        <span className="font-medium">Email:</span> {(() => {
                          const email = uploadResult.parsed_data.personal_info?.email || 
                                       uploadResult.parsed_data.email || 
                                       "";
                          return email || "Not available";
                        })()}
                      </div>
                      <div>
                        <span className="font-medium">Experience:</span> {(() => {
                          const exp = uploadResult.parsed_data.experience?.total_years || 
                                     uploadResult.parsed_data.experience_years ||
                                     uploadResult.parsed_data.total_years ||
                                     0;
                          return `${exp} years`;
                        })()}
                      </div>
                      <div>
                        <span className="font-medium">Skills:</span> {(() => {
                          let skillsCount = 0;
                          if (Array.isArray(uploadResult.parsed_data.skills)) {
                            skillsCount = uploadResult.parsed_data.skills.length;
                          } else if (uploadResult.parsed_data.skills) {
                            const skillsObj = uploadResult.parsed_data.skills;
                            skillsCount = (skillsObj.technical_skills?.length || 0) +
                                         (skillsObj.soft_skills?.length || 0) +
                                         (skillsObj.tools?.length || 0) +
                                         (skillsObj.languages?.length || 0) +
                                         (skillsObj.certifications?.length || 0);
                          }
                          return `${skillsCount} found`;
                        })()}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                      {(() => {
                        let skillsList: string[] = [];
                        
                        if (Array.isArray(uploadResult.parsed_data.skills)) {
                          skillsList = uploadResult.parsed_data.skills.map((s: any) =>
                            typeof s === 'string' ? s : s?.name
                          ).filter(Boolean);
                        } else if (uploadResult.parsed_data.skills) {
                          const skillsObj = uploadResult.parsed_data.skills;
                          skillsList = [
                            ...(skillsObj.technical_skills || []),
                            ...(skillsObj.soft_skills || []),
                            ...(skillsObj.tools || []),
                          ];
                        }
                        
                        return skillsList
                          .filter((skill: string) => skill && skill.trim().length > 0)
                          .slice(0, 12)
                          .map((skill: string, index: number) => (
                            <Badge key={index} variant="secondary" className="text-xs">
                              {skill}
                            </Badge>
                          ));
                      })()}
                    </div>

                    {uploadResult.screening_report && (
                      <div className="mt-3 p-3 rounded-md bg-white/60 border border-brand-teal/20 text-xs space-y-2">
                        <p className="font-medium text-brand-teal">Screening Summary</p>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <span className="font-medium">Confidence:</span>{' '}
                            {Math.round((uploadResult.screening_report.confidence || 0) * 100)}%
                          </div>
                          <div>
                            <span className="font-medium">Experience entries:</span>{' '}
                            {uploadResult.screening_report.experience_entries ?? 0}
                          </div>
                          <div>
                            <span className="font-medium">Education entries:</span>{' '}
                            {uploadResult.screening_report.education_entries ?? 0}
                          </div>
                          <div>
                            <span className="font-medium">Certifications:</span>{' '}
                            {uploadResult.screening_report.certificates_count ?? 0}
                          </div>
                        </div>
                        {uploadResult.pdf_extraction_method && (
                          <p>
                            <span className="font-medium">OCR/Extraction:</span>{' '}
                            {uploadResult.pdf_extraction_method}
                          </p>
                        )}
                        {uploadResult.raw_blob_ref && (
                          <p className="break-all">
                            <span className="font-medium">Azure Blob:</span>{' '}
                            {uploadResult.raw_blob_ref}
                          </p>
                        )}
                        {uploadResult.screening_report.completeness_grade && (
                          <div>
                            <span className="font-medium">Completeness:</span>{' '}
                            {uploadResult.screening_report.completeness_grade}
                            {uploadResult.screening_report.coverage_ratio != null && (
                              <> ({Math.round(uploadResult.screening_report.coverage_ratio * 100)}% coverage)</>
                            )}
                          </div>
                        )}
                        {(uploadResult.screening_report.section_inventory?.length ?? 0) > 0 && (
                          <div className="col-span-2">
                            <span className="font-medium">Sections found:</span>{' '}
                            {uploadResult.screening_report.section_inventory.slice(0, 8).join(', ')}
                            {uploadResult.screening_report.section_inventory.length > 8 ? '…' : ''}
                          </div>
                        )}
                        {(uploadResult.screening_report.gaps_for_hr_review?.length ?? 0) > 0 && (
                          <p className="text-amber-700 col-span-2">
                            <span className="font-medium">Needs HR review:</span>{' '}
                            {uploadResult.screening_report.gaps_for_hr_review.join(', ')}
                          </p>
                        )}
                        {(uploadResult.screening_report.missing_or_ambiguous_fields?.length ?? 0) > 0 &&
                          !(uploadResult.screening_report.gaps_for_hr_review?.length) && (
                          <p className="text-amber-700 col-span-2">
                            <span className="font-medium">Needs HR review:</span>{' '}
                            {uploadResult.screening_report.missing_or_ambiguous_fields.join(', ')}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Instructions */}
        <div className="text-sm text-brand-dark/70 bg-brand-light p-4 rounded-lg">
          <h4 className="font-medium mb-2">Enterprise Resume Screening:</h4>
          <ul className="space-y-1 text-xs">
            <li>• Supports PDF, Word, TXT, and scanned images — any layout, length, or section structure</li>
            <li>• Azure Document Intelligence (OCR) extracts full text including tables and multi-column layouts</li>
            <li>• AI agent inventories every section, role, skill, certification, project, and custom block</li>
            <li>• Verbatim raw-text indexing ensures nothing is missed for QuantChat and job matching</li>
            <li>• Original file stored in Azure Blob; parsed profile indexed in Postgres pgvector</li>
            <li>• Screening summary shows completeness grade and fields needing HR review</li>
          </ul>
        </div>

        {/* Notification */}
        {notification && (
          <div className={`fixed top-4 right-4 z-50 p-4 rounded-lg shadow-lg max-w-sm ${
            notification.type === 'success' 
              ? 'bg-brand-teal/15 border border-brand-teal/40 text-brand-teal' 
              : notification.type === 'error'
              ? 'bg-brand-red/15 border border-brand-red/40 text-brand-red'
              : 'bg-brand-gold/20 border border-brand-gold/40 text-brand-dark'
          }`}>
            <div className="flex items-center gap-2">
              {notification.type === 'success' && <CheckCircle className="h-5 w-5 text-brand-teal" />}
              {notification.type === 'error' && <AlertCircle className="h-5 w-5 text-brand-red" />}
              {notification.type === 'info' && <FileText className="h-5 w-5 text-brand-gold/80" />}
              <span className="text-sm font-medium">{notification.message}</span>
              <button 
                onClick={() => setNotification(null)}
                className="ml-auto text-brand-dark/60 hover:text-brand-dark"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

export default ResumeUpload;
