"use client";

import { useState, useRef } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { 
  MapPin, 
  Building2, 
  Briefcase, 
  Edit2, 
  Save, 
  X, 
  CheckCircle2,
  Code,
  Users,
  Gift,
  GraduationCap,
  Star,
  Download,
  FileText,
  Loader2
} from "lucide-react";
import { isEnterpriseFormat, type EnterpriseJobDescription } from "@/types/enterprise-jd";
import { EnterpriseJDPreviewCard } from "./enterprise-jd-preview-card";

// Legacy JD interface (for backward compatibility)
interface LegacyJD {
  title?: string;
  overview?: string;
  responsibilities?: string[];
  requirements?: {
    required?: string[];
    preferred?: string[];
  };
  skills?: {
    technical?: string[];
    soft?: string[];
  };
  benefits?: string[];
  sections?: any;
}

interface JDPreviewCardProps {
  jd: LegacyJD | EnterpriseJobDescription;
  jobDetails?: {
    department?: string;
    location?: string;
    remote_allowed?: boolean;
    job_level?: string;
    years_of_experience?: string;
    internal_title?: string;
    business_unit?: string;
    qualification?: string;
    skills?: string;
  };
  onSave?: (updatedJD: any) => void;
  onUpdate?: (updatedJD: any) => void;
  onPersisted?: (updatedJD: any) => void;
  onUnsavedChange?: (hasUnsavedChanges: boolean) => void;
  isEditable?: boolean;
}

export function JDPreviewCard({ 
  jd, 
  jobDetails, 
  onSave, 
  onUpdate,
  onPersisted,
  onUnsavedChange,
  isEditable = true 
}: JDPreviewCardProps) {
  const legacyJD = jd as LegacyJD;
  const [isEditing, setIsEditing] = useState(false);
  const [editedJD, setEditedJD] = useState(legacyJD);
  const [isDownloading, setIsDownloading] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  // Check if JD is in enterprise format and render appropriate component.
  // Hooks stay above this return so React sees a stable hook order.
  if (isEnterpriseFormat(jd)) {
    return (
      <EnterpriseJDPreviewCard
        jd={jd as EnterpriseJobDescription}
        onSave={onSave}
        onUpdate={onUpdate}
        onPersisted={onPersisted}
        onUnsavedChange={onUnsavedChange}
        isEditable={isEditable}
      />
    );
  }

  const handleEdit = () => {
    setEditedJD({...legacyJD});
    setIsEditing(true);
  };

  const handleCancel = () => {
    setEditedJD(legacyJD);
    setIsEditing(false);
  };

  const handleSaveEdit = () => {
    if (onUpdate) {
      onUpdate(editedJD);
    }
    setIsEditing(false);
  };

  const handleFinalSave = () => {
    if (onSave) {
      onSave(isEditing ? editedJD : jd);
    }
  };

  const currentJD = isEditing ? editedJD : jd;

  // Helper: Add spaces between concatenated words (e.g., "EdgePlatformEngineer" → "Edge Platform Engineer")
  const addSpacesToConcatenatedWords = (text: string): string => {
    if (!text) return text;
    
    let cleaned = String(text);
    
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
    
    // Step 5: Normalize multiple spaces
    cleaned = cleaned.replace(/ {2,}/g, ' ');
    
    return cleaned.trim();
  };

  // Helper: Clean garbled text (spaces/ampersands between characters)
  const cleanGarbledText = (text: string): string => {
    if (!text) return text;
    
    // First, fix concatenated words (missing spaces)
    let cleaned = addSpacesToConcatenatedWords(text);
    
    // Normalize multiple spaces to single space
    cleaned = cleaned.replace(/\s+/g, ' ');
    
    // Handle ampersands between characters: "D&o&c" → "Doc"
    cleaned = cleaned.replace(/([a-zA-Z0-9])&+([a-zA-Z0-9])/g, '$1$2');
    
    // Handle spaces between single characters that form words
    const lines = cleaned.split('\n');
    const cleanedLines = lines.map(line => {
      const words = line.split(/\s+/);
      const cleanedWords: string[] = [];
      
      let i = 0;
      while (i < words.length) {
        // Check if this starts a garbled sequence (single-char "words")
        if (words[i].length === 1 && i + 1 < words.length && words[i + 1].length === 1) {
          const garbledSeq = [words[i]];
          i += 1;
          while (i < words.length && words[i].length === 1) {
            garbledSeq.push(words[i]);
            i += 1;
          }
          cleanedWords.push(garbledSeq.join(''));
        } else {
          cleanedWords.push(words[i]);
          i += 1;
        }
      }
      
      return cleanedWords.join(' ');
    });
    
    cleaned = cleanedLines.join('\n');
    
    // Handle mixed spaces and ampersands
    cleaned = cleaned.replace(/([a-zA-Z0-9])\s*&\s*([a-zA-Z0-9])/g, '$1$2');
    
    // Clean up multiple spaces
    cleaned = cleaned.replace(/ {2,}/g, ' ');
    
    // Normalize line breaks
    cleaned = cleaned.replace(/\n{3,}/g, '\n\n');
    
    return cleaned.trim();
  };

  // Generate PDF content and download
  const handleDownloadPDF = async () => {
    setIsDownloading(true);
    
    try {
      // Dynamically import jspdf
      const { jsPDF } = await import('jspdf');
      
      const doc = new jsPDF();
      const pageWidth = doc.internal.pageSize.getWidth();
      const margin = 20;
      const contentWidth = pageWidth - (margin * 2);
      let yPos = 20;
      
      // Helper function to add text with word wrap
      const addText = (text: string, fontSize: number, isBold: boolean = false, color: [number, number, number] = [0, 0, 0]) => {
        // Clean garbled text (spaces/ampersands between characters)
        const cleanedText = cleanGarbledText(String(text || '').trim());
        if (!cleanedText) return;
        
        doc.setFontSize(fontSize);
        doc.setFont("helvetica", isBold ? "bold" : "normal");
        doc.setTextColor(color[0], color[1], color[2]);
        const lines = doc.splitTextToSize(cleanedText, contentWidth);
        doc.text(lines, margin, yPos);
        yPos += (lines.length * fontSize * 0.4) + 4;
        
        // Check if we need a new page
        if (yPos > 270) {
          doc.addPage();
          yPos = 20;
        }
      };
      
      // Helper function to add a section header
      const addSectionHeader = (title: string) => {
        yPos += 4;
        doc.setFillColor(240, 240, 240);
        doc.rect(margin - 2, yPos - 5, contentWidth + 4, 10, 'F');
        addText(title, 12, true, [50, 50, 50]);
        yPos += 2;
      };
      
      // Helper function to add bullet points
      const addBulletPoints = (items: string[]) => {
        items.forEach((item) => {
          // Clean garbled text (spaces/ampersands between characters)
          const cleanedItem = cleanGarbledText(String(item || '').trim());
          if (!cleanedItem) return;
          
          doc.setFontSize(10);
          doc.setFont("helvetica", "normal");
          doc.setTextColor(60, 60, 60);
          const bulletText = `• ${cleanedItem}`;
          const lines = doc.splitTextToSize(bulletText, contentWidth - 5);
          doc.text(lines, margin + 3, yPos);
          yPos += (lines.length * 4) + 3;
          
          if (yPos > 270) {
            doc.addPage();
            yPos = 20;
          }
        });
      };
      
      // Title
      doc.setFillColor(34, 139, 34); // Green header
      doc.rect(0, 0, pageWidth, 35, 'F');
      doc.setTextColor(255, 255, 255);
      doc.setFontSize(20);
      doc.setFont("helvetica", "bold");
      doc.text(currentJD.title || "Job Description", margin, 22);
      
      // Meta info
      doc.setFontSize(10);
      doc.setFont("helvetica", "normal");
      const metaInfo = [
        jobDetails?.department,
        jobDetails?.location,
        jobDetails?.job_level,
        jobDetails?.remote_allowed ? "Remote OK" : null
      ].filter(Boolean).join(" | ");
      doc.text(metaInfo, margin, 30);
      
      yPos = 45;
      doc.setTextColor(0, 0, 0);
      
      // Overview
      if (currentJD.overview) {
        addSectionHeader("📋 Overview");
        addText(currentJD.overview, 10, false, [60, 60, 60]);
      }
      
      // Technical Skills
      if (currentJD.skills?.technical && currentJD.skills.technical.length > 0) {
        addSectionHeader("💻 Technical Skills");
        addText(currentJD.skills.technical.join(" • "), 10, false, [30, 100, 180]);
      }
      
      // Soft Skills
      if (currentJD.skills?.soft && currentJD.skills.soft.length > 0) {
        addSectionHeader("🤝 Soft Skills");
        addText(currentJD.skills.soft.join(" • "), 10, false, [120, 60, 150]);
      }
      
      // Responsibilities
      if (currentJD.responsibilities && currentJD.responsibilities.length > 0) {
        addSectionHeader("📌 Key Responsibilities");
        addBulletPoints(currentJD.responsibilities);
      }
      
      // Required Qualifications
      if (currentJD.requirements?.required && currentJD.requirements.required.length > 0) {
        addSectionHeader("✅ Required Qualifications");
        addBulletPoints(currentJD.requirements.required);
      }
      
      // Preferred Qualifications
      if (currentJD.requirements?.preferred && currentJD.requirements.preferred.length > 0) {
        addSectionHeader("⭐ Preferred Qualifications");
        addBulletPoints(currentJD.requirements.preferred);
      }
      
      // Benefits
      if (currentJD.benefits && currentJD.benefits.length > 0) {
        addSectionHeader("🎁 Benefits");
        addBulletPoints(currentJD.benefits);
      }
      
      // Footer
      const pageCount = doc.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.setTextColor(150, 150, 150);
        doc.text(
          `Generated by QuantHire AI | Page ${i} of ${pageCount}`,
          pageWidth / 2,
          285,
          { align: 'center' }
        );
      }
      
      // Download
      const fileName = `${(currentJD.title || 'Job_Description').replace(/\s+/g, '_')}_JD.pdf`;
      doc.save(fileName);
      
    } catch (error) {
      console.error('Error generating PDF:', error);
      // Fallback: Use browser print
      handlePrintPDF();
    } finally {
      setIsDownloading(false);
    }
  };

  // Fallback: Print-based PDF generation
  const handlePrintPDF = () => {
    const printContent = generatePrintHTML();
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(printContent);
      printWindow.document.close();
      printWindow.focus();
      setTimeout(() => {
        printWindow.print();
        printWindow.close();
      }, 250);
    }
  };

  // Generate HTML for print
  const generatePrintHTML = () => {
    return `
      <!DOCTYPE html>
      <html>
      <head>
        <title>${currentJD.title || 'Job Description'}</title>
        <style>
          body { font-family: Arial, sans-serif; padding: 40px; max-width: 800px; margin: 0 auto; }
          h1 { color: #228B22; border-bottom: 3px solid #228B22; padding-bottom: 10px; }
          .meta { color: #666; margin-bottom: 20px; }
          h2 { color: #333; margin-top: 25px; border-left: 4px solid #228B22; padding-left: 10px; }
          ul { margin: 10px 0; }
          li { margin: 5px 0; color: #444; }
          .skills { display: flex; flex-wrap: wrap; gap: 8px; }
          .skill-badge { background: #e3f2fd; color: #1976d2; padding: 4px 12px; border-radius: 15px; font-size: 12px; }
          .soft-skill { background: #f3e5f5; color: #7b1fa2; }
          .footer { margin-top: 40px; text-align: center; color: #999; font-size: 12px; border-top: 1px solid #eee; padding-top: 20px; }
          @media print { body { padding: 20px; } }
        </style>
      </head>
      <body>
        <h1>${currentJD.title || 'Job Description'}</h1>
        <div class="meta">
          ${[jobDetails?.department, jobDetails?.location, jobDetails?.job_level, jobDetails?.remote_allowed ? 'Remote OK' : ''].filter(Boolean).join(' | ')}
        </div>
        
        ${currentJD.overview ? `<h2>Overview</h2><p>${currentJD.overview}</p>` : ''}
        
        ${currentJD.skills?.technical?.length ? `
          <h2>Technical Skills</h2>
          <div class="skills">
            ${currentJD.skills.technical.map(s => `<span class="skill-badge">${s}</span>`).join('')}
          </div>
        ` : ''}
        
        ${currentJD.skills?.soft?.length ? `
          <h2>Soft Skills</h2>
          <div class="skills">
            ${currentJD.skills.soft.map(s => `<span class="skill-badge soft-skill">${s}</span>`).join('')}
          </div>
        ` : ''}
        
        ${currentJD.responsibilities?.length ? `
          <h2>Key Responsibilities</h2>
          <ul>${currentJD.responsibilities.map(r => `<li>${r}</li>`).join('')}</ul>
        ` : ''}
        
        ${currentJD.requirements?.required?.length ? `
          <h2>Required Qualifications</h2>
          <ul>${currentJD.requirements.required.map(r => `<li>${r}</li>`).join('')}</ul>
        ` : ''}
        
        ${currentJD.requirements?.preferred?.length ? `
          <h2>Preferred Qualifications</h2>
          <ul>${currentJD.requirements.preferred.map(r => `<li>${r}</li>`).join('')}</ul>
        ` : ''}
        
        ${currentJD.benefits?.length ? `
          <h2>Benefits</h2>
          <ul>${currentJD.benefits.map(b => `<li>${b}</li>`).join('')}</ul>
        ` : ''}
        
        <div class="footer">Generated by QuantHire AI</div>
      </body>
      </html>
    `;
  };

  return (
    <Card className="w-full border-2 border-green-200 bg-gradient-to-br from-white to-green-50/30">
      {/* Header */}
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            {isEditing ? (
              <Input
                value={editedJD.title || ""}
                onChange={(e) => setEditedJD({...editedJD, title: e.target.value})}
                className="text-xl font-bold mb-2"
                placeholder="Job Title"
              />
            ) : (
              <CardTitle className="text-xl flex items-center gap-2">
                <CheckCircle2 className="h-5 w-5 text-green-600" />
                {currentJD.title || "Job Title"}
              </CardTitle>
            )}
            
            {/* Job Meta Info */}
            <div className="flex flex-wrap gap-3 mt-2 text-sm text-muted-foreground">
              {jobDetails?.department && (
                <span className="flex items-center gap-1">
                  <Building2 className="h-4 w-4" />
                  {jobDetails.department}
                </span>
              )}
              {jobDetails?.location && (
                <span className="flex items-center gap-1">
                  <MapPin className="h-4 w-4" />
                  {jobDetails.location}
                </span>
              )}
              {jobDetails?.job_level && (
                <span className="flex items-center gap-1">
                  <Briefcase className="h-4 w-4" />
                  {jobDetails.job_level}
                </span>
              )}
              {jobDetails?.remote_allowed && (
                <Badge variant="outline" className="text-green-600 border-green-300">
                  Remote OK
                </Badge>
              )}
            </div>
          </div>
          
          {/* Edit Button */}
          {isEditable && !isEditing && (
            <Button variant="outline" size="sm" onClick={handleEdit}>
              <Edit2 className="h-4 w-4 mr-1" />
              Edit
            </Button>
          )}
          {isEditing && (
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={handleCancel}>
                <X className="h-4 w-4 mr-1" />
                Cancel
              </Button>
              <Button size="sm" onClick={handleSaveEdit}>
                <Save className="h-4 w-4 mr-1" />
                Done
              </Button>
            </div>
          )}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Overview */}
        <div>
          <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
            <Star className="h-4 w-4 text-yellow-500" />
            Overview
          </Label>
          {isEditing ? (
            <Textarea
              value={editedJD.overview || ""}
              onChange={(e) => setEditedJD({...editedJD, overview: e.target.value})}
              rows={3}
              className="text-sm"
            />
          ) : (
            <p className="text-sm text-muted-foreground leading-relaxed">
              {currentJD.overview || "No overview provided"}
            </p>
          )}
        </div>

        {/* Divider */}
        <div className="border-t my-2" />

        {/* Technical Skills - Key Terms */}
        {((currentJD.skills?.technical?.length ?? 0) > 0 || isEditing) && (
          <div>
            <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
              <Code className="h-4 w-4 text-blue-500" />
              Technical Skills
            </Label>
            {isEditing ? (
              <Textarea
                rows={4}
                value={(editedJD.skills?.technical || []).join("\n")}
                onChange={(e) => setEditedJD({
                  ...editedJD,
                  skills: {
                    ...editedJD.skills,
                    technical: e.target.value.split("\n").map(s => s.trim()).filter(s => s)
                  }
                })}
                placeholder="Python\nTensorFlow\nFastAPI\n(one per line)"
              />
            ) : (
              <div className="flex flex-wrap gap-2">
                {currentJD.skills?.technical?.map((skill, idx) => (
                  <Badge key={idx} variant="secondary" className="bg-blue-100 text-blue-800 hover:bg-blue-200">
                    {skill}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Soft Skills */}
        {((currentJD.skills?.soft?.length ?? 0) > 0 || isEditing) && (
          <div>
            <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
              <Users className="h-4 w-4 text-purple-500" />
              Soft Skills
            </Label>
            {isEditing ? (
              <Textarea
                rows={4}
                value={(editedJD.skills?.soft || []).join("\n")}
                onChange={(e) => setEditedJD({
                  ...editedJD,
                  skills: {
                    ...editedJD.skills,
                    soft: e.target.value.split("\n").map(s => s.trim()).filter(s => s)
                  }
                })}
                placeholder="Communication\nLeadership\nTeamwork\n(one per line)"
              />
            ) : (
              <div className="flex flex-wrap gap-2">
                {currentJD.skills?.soft?.map((skill, idx) => (
                  <Badge key={idx} variant="outline" className="border-purple-300 text-purple-700">
                    {skill}
                  </Badge>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Divider */}
        <div className="border-t my-2" />

        {/* Responsibilities */}
        {((currentJD.responsibilities?.length ?? 0) > 0 || isEditing) && (
          <div>
            <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
              <Briefcase className="h-4 w-4 text-orange-500" />
              Key Responsibilities
            </Label>
            {isEditing ? (
              <Textarea
                value={(editedJD.responsibilities || []).join("\n")}
                onChange={(e) => setEditedJD({
                  ...editedJD,
                  responsibilities: e.target.value.split("\n").filter(r => r.trim())
                })}
                rows={4}
                placeholder="One responsibility per line"
              />
            ) : (
              <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                {currentJD.responsibilities?.slice(0, 5).map((resp, idx) => (
                  <li key={idx}>{resp}</li>
                ))}
                {(currentJD.responsibilities?.length || 0) > 5 && (
                  <li className="text-blue-600">+{currentJD.responsibilities!.length - 5} more...</li>
                )}
              </ul>
            )}
          </div>
        )}

        {/* Requirements */}
        {((currentJD.requirements?.required?.length ?? 0) > 0 || isEditing) && (
          <div>
            <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
              <GraduationCap className="h-4 w-4 text-green-500" />
              Requirements
            </Label>
            {isEditing ? (
              <Textarea
                value={(editedJD.requirements?.required || []).join("\n")}
                onChange={(e) => setEditedJD({
                  ...editedJD,
                  requirements: {
                    ...editedJD.requirements,
                    required: e.target.value.split("\n").filter(r => r.trim())
                  }
                })}
                rows={3}
                placeholder="One requirement per line"
              />
            ) : (
              <ul className="text-sm text-muted-foreground space-y-1 list-disc list-inside">
                {currentJD.requirements?.required?.slice(0, 4).map((req, idx) => (
                  <li key={idx}>{req}</li>
                ))}
                {(currentJD.requirements?.required?.length || 0) > 4 && (
                  <li className="text-blue-600">+{currentJD.requirements!.required!.length - 4} more...</li>
                )}
              </ul>
            )}
          </div>
        )}

        {/* Benefits */}
        {((currentJD.benefits?.length ?? 0) > 0 || isEditing) && (
          <div>
            <Label className="text-sm font-semibold flex items-center gap-1 mb-2">
              <Gift className="h-4 w-4 text-pink-500" />
              Benefits
            </Label>
            {isEditing ? (
              <Textarea
                value={(editedJD.benefits || []).join("\n")}
                onChange={(e) => setEditedJD({
                  ...editedJD,
                  benefits: e.target.value.split("\n").filter(b => b.trim())
                })}
                rows={3}
                placeholder="One benefit per line"
              />
            ) : (
              <div className="flex flex-wrap gap-2">
                {currentJD.benefits?.slice(0, 6).map((benefit, idx) => (
                  <Badge key={idx} variant="outline" className="border-pink-300 text-pink-700 text-xs">
                    {benefit.length > 30 ? benefit.substring(0, 30) + "..." : benefit}
                  </Badge>
                ))}
                {(currentJD.benefits?.length || 0) > 6 && (
                  <Badge variant="outline" className="text-xs">+{currentJD.benefits!.length - 6} more</Badge>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>

      {/* Footer with Save and Download Buttons */}
      <CardFooter className="border-t bg-muted/30 pt-4 flex flex-col gap-2">
        <div className="flex gap-2 w-full">
          <Button 
            variant="outline"
            className="flex-1" 
            onClick={handleDownloadPDF}
            disabled={isEditing || isDownloading}
          >
            {isDownloading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Generating PDF...
              </>
            ) : (
              <>
                <Download className="h-4 w-4 mr-2" />
                Download PDF
              </>
            )}
          </Button>
          <Button 
            variant="outline"
            className="flex-1" 
            onClick={handlePrintPDF}
            disabled={isEditing}
          >
            <FileText className="h-4 w-4 mr-2" />
            Print
          </Button>
        </div>
        {onSave && (
          <Button 
            className="w-full" 
            onClick={handleFinalSave}
            disabled={isEditing}
          >
            <Save className="h-4 w-4 mr-2" />
            Save Job to Database
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
