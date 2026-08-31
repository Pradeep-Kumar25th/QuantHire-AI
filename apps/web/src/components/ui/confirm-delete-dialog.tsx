"use client";

import * as React from "react";
import { Trash2, AlertTriangle, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export interface ConfirmDeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  warningNote?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => Promise<void> | void;
  isDeleting?: boolean;
}

export function ConfirmDeleteDialog({
  open,
  onOpenChange,
  title,
  description = "This removes the listing and its indexed data from QuantChat and matching. This cannot be undone.",
  warningNote,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  onConfirm,
  isDeleting = false,
}: ConfirmDeleteDialogProps) {
  const [internalLoading, setInternalLoading] = React.useState(false);
  const loading = isDeleting || internalLoading;

  const handleConfirm = async () => {
    try {
      setInternalLoading(true);
      await onConfirm();
    } finally {
      setInternalLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={loading ? undefined : onOpenChange}>
      <DialogContent className="sm:max-w-[440px] p-0 overflow-hidden border border-border/60 bg-background/95 backdrop-blur-xl shadow-2xl rounded-2xl">
        <div className="p-6 space-y-4">
          {/* Icon and Title Header */}
          <div className="flex items-start gap-4">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-red-500/10 text-red-600 dark:bg-red-950/40 dark:text-red-400 border border-red-500/20">
              <Trash2 className="h-5 w-5" />
            </div>
            <div className="space-y-1.5 pt-0.5">
              <DialogTitle className="text-lg font-semibold tracking-tight text-foreground">
                {title}
              </DialogTitle>
              <DialogDescription className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </DialogDescription>
            </div>
          </div>

          {warningNote && (
            <div className="flex items-start gap-2.5 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-200">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
              <span>{warningNote}</span>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <DialogFooter className="flex-row items-center justify-end gap-2.5 border-t border-border/50 bg-muted/30 px-6 py-3.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onOpenChange(false)}
            disabled={loading}
            className="rounded-xl px-4 font-medium"
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={handleConfirm}
            disabled={loading}
            className="rounded-xl px-4 font-medium bg-red-600 hover:bg-red-700 text-white shadow-sm shadow-red-500/20"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deleting...
              </>
            ) : (
              confirmLabel
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
