"use client";

import type { KeyboardEvent, MouseEvent } from "react";
import { useRouter } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  MapPin,
  Users,
  Calendar,
  Edit,
  Sparkles,
  Briefcase,
  Layers,
  Trash2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { JobCardPreviewData } from "@/lib/job-card-preview";

interface JobCardProps {
  job: {
    id: string;
    title: string;
    department: string;
    location: string;
    remote: boolean;
    status: string;
    openings: number;
    filled: number;
    applications: number;
    created: string;
    description?: string;
    requirements?: string[];
    hasEnterpriseJd?: boolean;
    preview?: JobCardPreviewData;
  };
  onEdit?: (job: JobCardProps["job"]) => void;
  onOpenJd?: (jobId: string) => void;
  onDelete?: (job: JobCardProps["job"]) => void;
}

const STATUS_STYLES: Record<string, string> = {
  open: "bg-emerald-600 hover:bg-emerald-600 text-white",
  draft: "bg-slate-700 hover:bg-slate-700 text-white",
  paused: "bg-amber-500 hover:bg-amber-500 text-white",
  closed: "bg-rose-600 hover:bg-rose-600 text-white",
  filled: "bg-blue-600 hover:bg-blue-600 text-white",
};

function WorkModelBadge({ workModel }: { workModel?: string }) {
  if (!workModel) return null;

  const styles =
    workModel === "Remote"
      ? "border-sky-200 bg-sky-50 text-sky-700"
      : workModel === "Hybrid"
        ? "border-violet-200 bg-violet-50 text-violet-700"
        : "border-orange-200 bg-orange-50 text-orange-700";

  return (
    <Badge variant="outline" className={`text-[10px] font-medium ${styles}`}>
      {workModel}
    </Badge>
  );
}

export function JobCard({ job, onEdit, onOpenJd, onDelete }: JobCardProps) {
  const router = useRouter();
  const preview = job.preview;
  const displayTitle = preview?.title || job.title;
  const displayDepartment = preview?.departmentDisplay || job.department;
  const displayLocation = preview?.locationLabel || job.location;
  const displayRemote = preview?.remote ?? job.remote;
  const statusClass =
    STATUS_STYLES[job.status] || "bg-secondary text-secondary-foreground";

  const handleCardClick = () => {
    if (job.hasEnterpriseJd && onOpenJd) {
      onOpenJd(job.id);
      return;
    }
    router.push(`/dashboard/jobs/${job.id}`);
  };

  const handleEditClick = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (job.hasEnterpriseJd && onOpenJd) {
      onOpenJd(job.id);
      return;
    }
    onEdit?.(job);
  };

  const handleDeleteClick = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDelete?.(job);
  };

  return (
    <Card
      className={`group relative overflow-hidden border transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg cursor-pointer ${
        job.hasEnterpriseJd
          ? "border-teal-200/80 bg-gradient-to-b from-teal-50/40 via-background to-background hover:border-teal-300"
          : "hover:border-primary/40"
      }`}
      onClick={handleCardClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e: KeyboardEvent) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleCardClick();
        }
      }}
    >
      {job.hasEnterpriseJd && (
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-teal-500 via-emerald-500 to-cyan-500" />
      )}

      {(onEdit || onOpenJd || onDelete) && (
        <div className="absolute top-3 right-3 z-10 flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
          {onDelete && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-full bg-background/80 text-rose-600 shadow-sm backdrop-blur hover:text-rose-700 hover:bg-rose-50"
              onClick={handleDeleteClick}
              aria-label="Delete job"
              title="Delete job"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          )}
          {(onEdit || onOpenJd) && (
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-full bg-background/80 shadow-sm backdrop-blur"
              onClick={handleEditClick}
              aria-label={
                job.hasEnterpriseJd ? "Edit AI job description" : "Edit job"
              }
            >
              <Edit className="h-4 w-4" />
            </Button>
          )}
        </div>
      )}

      <CardHeader className="space-y-2 pb-2 pt-4">
        <div className="flex items-start justify-between gap-2 pr-8">
          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex flex-wrap items-center gap-1.5">
              {job.hasEnterpriseJd && (
                <Badge
                  variant="outline"
                  className="border-teal-200 bg-teal-50 text-[10px] font-semibold uppercase tracking-wide text-teal-700"
                >
                  <Sparkles className="mr-1 h-3 w-3" />
                  AI JD
                </Badge>
              )}
              {preview?.level && (
                <Badge variant="secondary" className="text-[10px] font-medium">
                  {preview.level}
                </Badge>
              )}
              {preview && preview.customSectionCount > 0 && (
                <Badge variant="outline" className="text-[10px]">
                  +{preview.customSectionCount} custom
                </Badge>
              )}
            </div>

            <CardTitle className="text-base leading-snug tracking-tight line-clamp-2">
              {displayTitle}
            </CardTitle>
          </div>

          <Badge className={`shrink-0 capitalize text-[10px] px-2 py-0.5 ${statusClass}`}>
            {job.status}
          </Badge>
        </div>

        <div className="space-y-1">
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <Briefcase className="h-3.5 w-3.5 shrink-0 text-teal-600" />
            <span className="line-clamp-1 font-medium text-foreground/80">
              {displayDepartment}
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3.5 w-3.5 shrink-0" />
            <span className="line-clamp-1">{displayLocation}</span>
            <WorkModelBadge workModel={preview?.workModel} />
            {displayRemote && !preview?.workModel && (
              <Badge variant="outline" className="text-[10px]">
                Remote
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-2.5 pb-4 pt-0">
        {preview?.summary && (
          <p className="line-clamp-2 text-xs leading-relaxed text-muted-foreground">
            {preview.summary}
          </p>
        )}

        {preview && preview.skillTags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {preview.skillTags.slice(0, 3).map((skill) => (
              <Badge
                key={skill}
                variant="secondary"
                className="rounded-full px-1.5 py-0 text-[9px] font-normal"
              >
                {skill}
              </Badge>
            ))}
            {preview.skillTags.length > 3 && (
              <Badge variant="outline" className="rounded-full px-1.5 py-0 text-[9px] font-normal">
                +{preview.skillTags.length - 3}
              </Badge>
            )}
          </div>
        )}

        <div className="grid grid-cols-2 gap-2 rounded-md border bg-muted/30 p-2 text-xs">
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Users className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{job.applications} apps</span>
          </div>
          <div className="flex items-center gap-1.5 text-muted-foreground">
            <Calendar className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{new Date(job.created).toLocaleDateString()}</span>
          </div>
        </div>

        <div className="flex items-center justify-between border-t pt-2">
          <div>
            <p className="text-xs font-semibold">
              {job.filled} / {job.openings} filled
            </p>
            {job.hasEnterpriseJd && preview && preview.removedSectionCount > 0 && (
              <p className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                <Layers className="h-3 w-3" />
                Customized JD ({preview.removedSectionCount} sections hidden)
              </p>
            )}
          </div>
          {job.hasEnterpriseJd && (
            <span className="text-xs font-medium text-teal-700 opacity-0 transition-opacity group-hover:opacity-100">
              View / edit JD
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
