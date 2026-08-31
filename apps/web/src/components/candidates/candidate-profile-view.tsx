"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Award,
  Briefcase,
  Calendar,
  ExternalLink,
  GraduationCap,
  Mail,
  MapPin,
  MessageSquare,
  Phone,
  Sparkles,
  Target,
  AlertTriangle,
  Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type CandidateDetail,
  buildCandidateQuantChatPrompt,
  formatCandidateSource,
  getCandidateInitials,
} from "@/lib/candidate-mapper";
import { openQuantChatWithPrompt } from "@/lib/quantchat-bridge";
import { ConfirmDeleteDialog } from "@/components/ui/confirm-delete-dialog";
import { api } from "@/lib/api";

import * as React from "react";

interface CandidateProfileViewProps {
  candidate: CandidateDetail;
}

function formatExperienceYears(years: number): string | null {
  if (!years || years <= 0) return null;
  if (years < 1) return "< 1 year experience";
  const rounded = Math.round(years * 10) / 10;
  return `${rounded} year${rounded === 1 ? "" : "s"} experience`;
}

function groupSkillsByCategory(skills: CandidateDetail["skills"]) {
  const groups: Record<string, CandidateDetail["skills"]> = {};
  for (const skill of skills) {
    const key = skill.category || "technical";
    if (!groups[key]) groups[key] = [];
    groups[key].push(skill);
  }
  return groups;
}

function formatCategoryLabel(category: string): string {
  return category
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export function CandidateProfileView({ candidate }: CandidateProfileViewProps) {
  const router = useRouter();
  const initials = getCandidateInitials(candidate.name);
  const experienceLabel = formatExperienceYears(candidate.experienceYears);
  const skillGroups = groupSkillsByCategory(candidate.skills);
  const confidence = candidate.parsingConfidence;

  const handleAskQuantChat = () => {
    openQuantChatWithPrompt(buildCandidateQuantChatPrompt(candidate), { autoSend: true });
  };

  const handleMatchToJob = () => {
    const params = new URLSearchParams({
      candidateId: candidate.id,
      candidateName: candidate.name,
    });
    router.push(`/dashboard/job-matching?${params.toString()}`);
  };

  const [showDeleteDialog, setShowDeleteDialog] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);

  const handleRemoveCandidate = () => {
    setShowDeleteDialog(true);
  };

  const executeRemoveCandidate = async () => {
    try {
      setIsDeleting(true);
      await api.candidates.delete(candidate.id);
      setShowDeleteDialog(false);
      router.push("/dashboard/candidates");
    } catch (error: any) {
      const status = error?.response?.status;
      if (status === 204 || status === 200 || status === 404) {
        setShowDeleteDialog(false);
        router.push("/dashboard/candidates");
      } else {
        console.error("Failed to remove candidate:", error);
        setShowDeleteDialog(false);
        router.push("/dashboard/candidates");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-4 sm:p-6 lg:p-8">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" asChild className="-ml-2">
          <Link href="/dashboard/candidates">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to candidates
          </Link>
        </Button>
        {!candidate.isActive && (
          <Badge variant="outline" className="border-amber-300 text-amber-800">
            Inactive
          </Badge>
        )}
        {candidate.source && (
          <Badge variant="secondary">
            Source: {formatCandidateSource(candidate.source)}
          </Badge>
        )}
      </div>

      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 items-start gap-4">
          <div
            className="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-[#CC112F]/15 to-[#437A8B]/20 text-lg font-bold text-[#363636] ring-1 ring-[#437A8B]/20"
            aria-hidden
          >
            {initials}
          </div>
          <div className="min-w-0 space-y-2">
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{candidate.name}</h1>
            {candidate.headline && (
              <p className="text-sm text-muted-foreground">{candidate.headline}</p>
            )}
            <div className="flex flex-wrap gap-x-4 gap-y-2 text-sm text-muted-foreground">
              {candidate.displayEmail && (
                <span className="inline-flex items-center gap-1.5 min-w-0">
                  <Mail className="h-4 w-4 shrink-0 text-[#437A8B]" />
                  <span className="truncate">{candidate.displayEmail}</span>
                </span>
              )}
              {candidate.phone && (
                <span className="inline-flex items-center gap-1.5">
                  <Phone className="h-4 w-4 shrink-0" />
                  {candidate.phone}
                </span>
              )}
              {candidate.location && (
                <span className="inline-flex items-center gap-1.5">
                  <MapPin className="h-4 w-4 shrink-0" />
                  {candidate.location}
                </span>
              )}
              {experienceLabel && (
                <span className="inline-flex items-center gap-1.5">
                  <Briefcase className="h-4 w-4 shrink-0" />
                  {experienceLabel}
                </span>
              )}
              {candidate.uploadedAt && (
                <span className="inline-flex items-center gap-1.5">
                  <Calendar className="h-4 w-4 shrink-0" />
                  Added {candidate.uploadedAt}
                </span>
              )}
            </div>
            {candidate.links.length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {candidate.links.map((link) => (
                  <a
                    key={link.url}
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Badge
                      variant="outline"
                      className="cursor-pointer gap-1 hover:border-[#437A8B]/50 hover:bg-[#437A8B]/5"
                    >
                      <ExternalLink className="h-3 w-3" />
                      {link.label}
                    </Badge>
                  </a>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 shrink-0">
          <Button
            variant="outline"
            onClick={handleAskQuantChat}
            className="border-[#437A8B]/40"
          >
            <MessageSquare className="mr-2 h-4 w-4 text-[#437A8B]" />
            Ask QuantChat
          </Button>
          <Button onClick={handleMatchToJob} className="malomatia-cta-gradient border-0 text-white">
            <Target className="mr-2 h-4 w-4" />
            Match to job
          </Button>
          {candidate.isActive && (
            <Button
              variant="outline"
              className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
              onClick={() => void handleRemoveCandidate()}
            >
              <Trash2 className="mr-2 h-4 w-4" />
              Remove from pool
            </Button>
          )}
        </div>
      </div>

      {confidence != null && (
        <Card className="border-[#437A8B]/30 bg-[#437A8B]/5">
          <CardContent className="flex flex-col gap-4 pt-6 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-semibold">AI parsing confidence</p>
              <p className="text-xs text-muted-foreground">
                Structured profile extracted from the uploaded resume
                {candidate.missingFields.length > 0
                  ? ` · ${candidate.missingFields.length} field(s) flagged for review`
                  : ""}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Progress value={confidence} className="h-2 w-32 sm:w-40" />
              <span className="text-2xl font-bold tabular-nums text-[#237690]">{confidence}%</span>
            </div>
          </CardContent>
        </Card>
      )}

      {candidate.missingFields.length > 0 && (
        <Card className="border-amber-200/80 bg-amber-50/50 dark:border-amber-900/40 dark:bg-amber-950/20">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base text-amber-900 dark:text-amber-200">
              <AlertTriangle className="h-4 w-4" />
              Fields to verify
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {candidate.missingFields.map((field) => (
                <Badge
                  key={field}
                  variant="outline"
                  className="border-amber-300/80 bg-white/70 text-amber-900 dark:bg-transparent dark:text-amber-100"
                >
                  {field}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList className="flex h-auto w-full flex-wrap justify-start gap-1">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="experience">
            Experience ({candidate.experience.length})
          </TabsTrigger>
          <TabsTrigger value="skills">Skills ({candidate.skillNames.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Professional summary</CardTitle>
            </CardHeader>
            <CardContent>
              {candidate.summary ? (
                <p className="leading-relaxed text-muted-foreground whitespace-pre-wrap">
                  {candidate.summary}
                </p>
              ) : (
                <p className="text-sm text-muted-foreground italic">
                  No summary was extracted. Review experience and skills tabs, or ask QuantChat
                  to summarize this profile.
                </p>
              )}
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <GraduationCap className="h-5 w-5 text-[#437A8B]" />
                  Education
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {candidate.education.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic">No education entries parsed.</p>
                ) : (
                  candidate.education.map((edu, index) => (
                    <div key={`${edu.degree}-${index}`} className="space-y-1">
                      <p className="font-medium">{edu.degree || "Qualification"}</p>
                      {edu.institution && (
                        <p className="text-sm text-muted-foreground">{edu.institution}</p>
                      )}
                      <p className="text-xs text-muted-foreground">
                        {[edu.year, edu.field, edu.gpa ? `GPA: ${edu.gpa}` : ""]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Award className="h-5 w-5 text-[#FFC000]" />
                  Certifications
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {candidate.certificates.length === 0 ? (
                  <p className="text-sm text-muted-foreground italic">
                    No certifications parsed.
                  </p>
                ) : (
                  candidate.certificates.map((cert, index) => (
                    <div key={`${cert.name}-${index}`} className="space-y-1">
                      <p className="text-sm font-medium">{cert.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {[cert.issuer, cert.date].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </div>

          {candidate.skillNames.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Top skills</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {candidate.skillNames.slice(0, 12).map((skill) => (
                    <Badge key={skill} variant="secondary">
                      {skill}
                    </Badge>
                  ))}
                  {candidate.skillNames.length > 12 && (
                    <Badge variant="outline">+{candidate.skillNames.length - 12} more</Badge>
                  )}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="experience" className="space-y-4">
          {candidate.experience.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                No work history was extracted from this resume yet.
              </CardContent>
            </Card>
          ) : (
            candidate.experience.map((exp, index) => (
              <Card key={`${exp.company}-${exp.title}-${index}`}>
                <CardHeader>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <CardTitle className="text-lg">{exp.title}</CardTitle>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {[exp.company, exp.location].filter(Boolean).join(" · ")}
                      </p>
                    </div>
                    {(exp.start || exp.end) && (
                      <Badge variant="outline" className="shrink-0 self-start">
                        {[exp.start, exp.end].filter(Boolean).join(" – ")}
                      </Badge>
                    )}
                  </div>
                </CardHeader>
                {exp.bullets.length > 0 && (
                  <CardContent>
                    <ul className="space-y-2">
                      {exp.bullets.map((bullet, bulletIndex) => (
                        <li key={bulletIndex} className="flex items-start gap-2 text-sm">
                          <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-[#437A8B]" />
                          <span className="text-muted-foreground">{bullet}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                )}
              </Card>
            ))
          )}
        </TabsContent>

        <TabsContent value="skills" className="space-y-4">
          {candidate.skills.length === 0 ? (
            <Card>
              <CardContent className="py-10 text-center text-sm text-muted-foreground">
                Skills will appear here once parsing completes.
              </CardContent>
            </Card>
          ) : (
            Object.entries(skillGroups).map(([category, skills]) => (
              <Card key={category}>
                <CardHeader>
                  <CardTitle className="text-base">{formatCategoryLabel(category)}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {skills.map((skill) => (
                    <div key={skill.name} className="space-y-1">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-sm font-medium">{skill.name}</span>
                        {skill.confidence != null && (
                          <span className="text-xs tabular-nums text-muted-foreground">
                            {skill.confidence}% confidence
                          </span>
                        )}
                      </div>
                      {skill.confidence != null && (
                        <Progress value={skill.confidence} className="h-1.5" />
                      )}
                    </div>
                  ))}
                </CardContent>
              </Card>
            ))
          )}
        </TabsContent>
      </Tabs>

      <Card className="border-dashed">
        <CardContent className="flex flex-col items-start gap-4 py-6 sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="flex items-center gap-2 text-sm font-semibold">
              <Sparkles className="h-4 w-4 text-[#CC112F]" />
              Ready for the next step?
            </p>
            <p className="text-sm text-muted-foreground">
              Run agentic job matching or ask QuantChat about this candidate using indexed
              resume data.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={handleAskQuantChat}>
              Ask QuantChat
            </Button>
            <Button onClick={handleMatchToJob} className="malomatia-cta-gradient border-0 text-white">
              Match to job
            </Button>
          </div>
        </CardContent>
      </Card>

      <ConfirmDeleteDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        title={`Remove "${candidate.name}"?`}
        description="Their resume will be hidden and removed from QuantChat and matching. This cannot be undone."
        confirmLabel="Remove Candidate"
        cancelLabel="Cancel"
        onConfirm={executeRemoveCandidate}
        isDeleting={isDeleting}
      />
    </div>
  );
}
