"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import ResumeUpload from "@/components/ResumeUpload";

interface UploadResumeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onUploadSuccess?: () => void;
}

export function UploadResumeDialog({
  open,
  onOpenChange,
  onUploadSuccess,
}: UploadResumeDialogProps) {
  const [key, setKey] = useState(0);

  const handleSuccess = () => {
    onUploadSuccess?.();
    onOpenChange(false);
    setKey((value) => value + 1);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Upload Resume</DialogTitle>
          <DialogDescription>
            Upload a resume to extract candidate details with Azure Document Intelligence and AI parsing.
          </DialogDescription>
        </DialogHeader>
        <ResumeUpload key={key} onUploadSuccess={handleSuccess} />
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
