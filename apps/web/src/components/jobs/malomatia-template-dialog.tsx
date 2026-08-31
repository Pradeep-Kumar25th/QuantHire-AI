"use client";

import { useEffect, useMemo, useState } from "react";
import { FileText, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  downloadMalomatiaTemplateDocx,
  recommendMalomatiaTemplate,
  templateTypeLabel,
  type MalomatiaTemplateType,
} from "@/lib/malomatia-template";
import type { EnterpriseJobDescription } from "@/types/enterprise-jd";

interface MalomatiaTemplateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  jd: EnterpriseJobDescription;
}

export function MalomatiaTemplateDialog({
  open,
  onOpenChange,
  jd,
}: MalomatiaTemplateDialogProps) {
  const recommendation = useMemo(() => recommendMalomatiaTemplate(jd), [jd]);
  const [selectedTemplate, setSelectedTemplate] = useState<MalomatiaTemplateType>(
    recommendation.templateType ?? "non_leader"
  );
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setSelectedTemplate(recommendation.templateType ?? "non_leader");
      setError(null);
    }
  }, [open, recommendation.templateType]);

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);
    try {
      await downloadMalomatiaTemplateDocx(jd, selectedTemplate);
      onOpenChange(false);
    } catch (exportError) {
      const message =
        exportError instanceof Error
          ? exportError.message
          : "Failed to generate Malomatia Word document.";
      setError(message);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Convert to Malomatia Template</DialogTitle>
          <DialogDescription>
            Export this job description as a Microsoft Word file using Malomatia&apos;s official
            JD template. Leader roles use Strategic, Operational, and People Management sections;
            Non-Leader roles use a single Operational duties list.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="rounded-md border bg-muted/40 p-3 text-sm">
            <p className="font-medium">Suggested template</p>
            <p className="mt-1 text-muted-foreground">{recommendation.reason}</p>
            {recommendation.yoeText ? (
              <p className="mt-2 text-xs text-muted-foreground">
                Experience source: {recommendation.yoeText}
              </p>
            ) : null}
          </div>

          <div className="grid gap-2 sm:grid-cols-2">
            {(["leader", "non_leader"] as const).map((templateType) => {
              const isSelected = selectedTemplate === templateType;
              return (
                <button
                  key={templateType}
                  type="button"
                  onClick={() => setSelectedTemplate(templateType)}
                  className={`rounded-lg border p-4 text-left transition-colors ${
                    isSelected
                      ? "border-primary bg-primary/5 ring-2 ring-primary/20"
                      : "hover:bg-muted/50"
                  }`}
                >
                  <p className="font-medium">{templateTypeLabel(templateType)}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {templateType === "leader"
                      ? "Strategic, Operational, and People Management sections."
                      : "Operational duties with numbered responsibilities."}
                  </p>
                </button>
              );
            })}
          </div>

          {recommendation.confidence === "ambiguous" ? (
            <p className="text-sm text-amber-700">
              This role crosses the 10-year threshold. Please confirm the correct template before
              downloading.
            </p>
          ) : null}

          {error ? <p className="text-sm text-red-600">{error}</p> : null}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isExporting}>
            Cancel
          </Button>
          <Button onClick={handleExport} disabled={isExporting}>
            {isExporting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating Word file...
              </>
            ) : (
              <>
                <FileText className="mr-2 h-4 w-4" />
                Download Word Document
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
