"use client";

import Link from "next/link";
import type { MouseEvent } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Briefcase, Calendar, MapPin, Mail, Users, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  formatCandidateUploadDate,
  getCandidateInitials,
} from "@/lib/candidate-mapper";

interface CandidateCardProps {
  candidate: {
    id: string;
    name: string;
    displayEmail: string | null;
    location: string;
    headline?: string;
    experience_years: number;
    skills: string[];
    active_applications: number;
    upload_date?: string;
  };
  onDelete?: (candidate: CandidateCardProps["candidate"]) => void;
}

function formatExperience(years: number): string | null {
  if (!years || years <= 0) return null;
  if (years < 1) return "< 1 yr";
  const rounded = Math.round(years * 10) / 10;
  return `${rounded}${rounded === 1 ? " yr" : " yrs"}`;
}

export function CandidateCard({ candidate, onDelete }: CandidateCardProps) {
  const initials = getCandidateInitials(candidate.name);
  const experienceLabel = formatExperience(candidate.experience_years);
  const skillCount = candidate.skills?.length ?? 0;
  const uploadedLabel = formatCandidateUploadDate(candidate.upload_date);

  const handleDeleteClick = (e: MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    onDelete?.(candidate);
  };

  return (
    <Link
      href={`/dashboard/candidates/${candidate.id}`}
      className="block h-full rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2"
    >
      <Card
        className={cn(
          "group relative h-full overflow-hidden border border-slate-200/80 bg-card shadow-sm transition-all duration-200",
          "hover:-translate-y-0.5 hover:border-violet-200/90 hover:shadow-md hover:shadow-violet-500/5",
          "dark:border-slate-800",
        )}
      >
        <div className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-violet-500 via-indigo-500 to-sky-500" />

        {onDelete && (
          <div className="absolute top-3 right-3 z-10 opacity-0 transition-opacity group-hover:opacity-100">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-full bg-background/80 text-rose-600 shadow-sm backdrop-blur hover:bg-rose-50 hover:text-rose-700"
              onClick={handleDeleteClick}
              aria-label="Remove candidate"
              title="Remove from talent pool"
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        )}

        <CardContent className="space-y-3 p-4 pt-5">
          <div className="flex items-start gap-3">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-violet-100 to-indigo-100 text-xs font-bold text-violet-800 ring-1 ring-violet-200/60 dark:from-violet-950 dark:to-indigo-950 dark:text-violet-200 dark:ring-violet-900"
              aria-hidden
            >
              {initials}
            </div>

            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <h3 className="text-sm font-semibold leading-snug tracking-tight line-clamp-2">
                  {candidate.name}
                </h3>
                {experienceLabel && (
                  <Badge
                    variant="secondary"
                    className="shrink-0 text-[10px] font-medium tabular-nums"
                  >
                    {experienceLabel}
                  </Badge>
                )}
              </div>

              {candidate.headline && (
                <p className="line-clamp-1 text-xs text-muted-foreground">
                  {candidate.headline}
                </p>
              )}
            </div>
          </div>

          <div className="space-y-1.5 text-xs text-muted-foreground">
            {candidate.displayEmail && (
              <div className="flex items-center gap-2 min-w-0">
                <Mail className="h-3.5 w-3.5 shrink-0 text-violet-600 dark:text-violet-400" />
                <span className="truncate">{candidate.displayEmail}</span>
              </div>
            )}

            <div className="flex items-center gap-2 min-w-0">
              <MapPin className="h-3.5 w-3.5 shrink-0" />
              <span className="line-clamp-1">
                {candidate.location || "Location not listed"}
              </span>
            </div>
          </div>

          {skillCount > 0 ? (
            <div className="flex flex-wrap gap-1 border-t border-slate-200/70 pt-2.5 dark:border-slate-800">
              {candidate.skills.slice(0, 3).map((skill) => (
                <Badge
                  key={skill}
                  variant="outline"
                  className="rounded-md border-slate-200/80 px-1.5 py-0 text-[10px] font-normal dark:border-slate-700"
                >
                  {skill}
                </Badge>
              ))}
              {skillCount > 3 && (
                <Badge
                  variant="outline"
                  className="rounded-md border-slate-200/80 px-1.5 py-0 text-[10px] font-normal dark:border-slate-700"
                >
                  +{skillCount - 3}
                </Badge>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 border-t border-slate-200/70 pt-2.5 text-[11px] text-muted-foreground dark:border-slate-800">
              <Briefcase className="h-3.5 w-3.5 shrink-0 opacity-70" />
              <span>Skills will appear after parsing completes</span>
            </div>
          )}

          <div className="flex items-center justify-between border-t border-slate-200/70 pt-2.5 text-[11px] dark:border-slate-800">
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Users className="h-3.5 w-3.5 shrink-0" />
                {candidate.active_applications} active
              </span>
              {uploadedLabel && (
                <span className="inline-flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5 shrink-0" />
                  {uploadedLabel}
                </span>
              )}
            </div>
            <span className="font-medium text-violet-700 opacity-0 transition-opacity group-hover:opacity-100 dark:text-violet-300">
              Open profile
            </span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
