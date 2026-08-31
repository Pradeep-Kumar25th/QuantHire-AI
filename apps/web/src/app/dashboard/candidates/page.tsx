"use client";

import { useState, useEffect, useMemo } from "react";
import { apiFetchJson } from "@/lib/api-client";
import {
  Upload,
  Search,
  RefreshCw,
  Users,
  Briefcase,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CandidateCard } from "@/components/candidates/candidate-card";
import ResumeUpload from "@/components/ResumeUpload";
import {
  mapCandidatesResponse,
  type DashboardCandidate,
} from "@/lib/candidate-mapper";
import { ConfirmDeleteDialog } from "@/components/ui/confirm-delete-dialog";
import { api } from "@/lib/api";

interface Candidate extends DashboardCandidate {}

function StatPill({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon: typeof Users;
}) {
  return (
    <div className="rounded-xl border bg-card/80 px-4 py-3 shadow-sm">
      <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mt-1 text-2xl font-bold tracking-tight">{value}</div>
    </div>
  );
}

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [showUpload, setShowUpload] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [listError, setListError] = useState<string | null>(null);
  const [candidateToDelete, setCandidateToDelete] = useState<Candidate | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const fetchCandidates = async (): Promise<boolean> => {
    try {
      setLoading(true);
      setListError(null);
      const data = await apiFetchJson<unknown>("/v1/candidates?is_active=true");
      setCandidates(mapCandidatesResponse(data));
      return true;
    } catch (error) {
      console.error("Error fetching candidates:", error);
      setCandidates([]);
      setListError(
        error instanceof Error ? error.message : "Failed to load candidates",
      );
      return false;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCandidates();
  }, []);

  const filteredCandidates = candidates.filter((candidate) => {
    const term = searchTerm.toLowerCase();
    return (
      (candidate.name || "").toLowerCase().includes(term) ||
      (candidate.displayEmail || "").toLowerCase().includes(term) ||
      (candidate.location || "").toLowerCase().includes(term) ||
      (candidate.headline || "").toLowerCase().includes(term) ||
      (candidate.skills || []).some((skill) =>
        (skill || "").toLowerCase().includes(term),
      )
    );
  });

  const stats = useMemo(() => {
    const withSkills = candidates.filter((c) => (c.skills?.length ?? 0) > 0).length;
    const withLocation = candidates.filter((c) => Boolean(c.location?.trim())).length;
    const activeApplications = candidates.reduce(
      (sum, c) => sum + (c.active_applications || 0),
      0,
    );
    const avgExperience =
      candidates.length > 0
        ? Math.round(
            candidates.reduce((sum, c) => sum + (c.experience_years || 0), 0) /
              candidates.length,
          )
        : 0;

    return { withSkills, withLocation, activeApplications, avgExperience };
  }, [candidates]);

  const handleUploadSuccess = async () => {
    const refreshed = await fetchCandidates();
    if (refreshed) {
      setShowUpload(false);
      return;
    }
    setListError(
      "Resume was parsed successfully, but the candidate list could not be refreshed. Use Refresh to retry.",
    );
  };

  const handleDeleteCandidate = (candidate: {
    id: string;
    name: string;
    active_applications: number;
  }) => {
    const candidateObj = candidates.find((c) => c.id === candidate.id) || {
      id: candidate.id,
      name: candidate.name,
      email: "",
      phone: null,
      skills: [],
      rawSkills: [],
      experienceYears: null,
      topRole: null,
      active_applications: candidate.active_applications,
      stage: "Sourced",
      matchScore: 0,
      isActive: true,
      lastUpdated: new Date().toISOString(),
      source: "upload" as const,
      avatarUrl: null,
      createdAt: new Date().toISOString(),
      status: "Available",
      education: [],
    };
    setCandidateToDelete(candidateObj as Candidate);
  };

  const executeDeleteCandidate = async () => {
    if (!candidateToDelete) return;
    try {
      setIsDeleting(true);
      await api.candidates.delete(candidateToDelete.id);
      setCandidateToDelete(null);
      await fetchCandidates();
    } catch (error: any) {
      const status = error?.response?.status;
      if (status === 204 || status === 200 || status === 404) {
        setCandidateToDelete(null);
        await fetchCandidates();
      } else {
        console.error("Failed to delete candidate:", error);
        setCandidateToDelete(null);
        await fetchCandidates();
      }
    } finally {
      setIsDeleting(false);
    }
  };

  if (showUpload) {
    return (
      <div className="flex-1 space-y-4 p-6 pt-6 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-2xl font-bold tracking-tight">Upload Resume</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Parse a resume into a searchable candidate profile.
            </p>
          </div>
          <Button variant="outline" onClick={() => setShowUpload(false)}>
            Back to Candidates
          </Button>
        </div>
        <ResumeUpload onUploadSuccess={handleUploadSuccess} />
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-5 p-6 pt-6 sm:p-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-3 min-w-0">
          <div className="rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 p-2.5 shadow-md shadow-violet-500/20 shrink-0">
            <Users className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0">
            <h2 className="text-2xl font-bold tracking-tight">Candidates</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Resume-backed talent profiles for matching and outreach.
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={fetchCandidates} disabled={loading}>
            <RefreshCw
              className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
          <Button onClick={() => setShowUpload(true)}>
            <Upload className="mr-2 h-4 w-4" />
            Upload Resume
          </Button>
        </div>
      </div>

      {!loading && candidates.length > 0 && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatPill label="Total profiles" value={candidates.length} icon={Users} />
          <StatPill label="With skills" value={stats.withSkills} icon={Sparkles} />
          <StatPill
            label="Active applications"
            value={stats.activeApplications}
            icon={Briefcase}
          />
          <StatPill
            label="Avg experience"
            value={stats.avgExperience > 0 ? `${stats.avgExperience} yrs` : "—"}
            icon={TrendingUp}
          />
        </div>
      )}

      <div className="flex items-center space-x-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by name, title, or skills (e.g. Python, Azure)…"
            className="pl-9"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {listError && (
        <div
          role="alert"
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300"
        >
          {listError}
        </div>
      )}

      {loading ? (
        <div className="flex h-64 items-center justify-center rounded-xl border bg-muted/20">
          <div className="text-center">
            <RefreshCw className="mx-auto mb-3 h-8 w-8 animate-spin text-violet-600" />
            <p className="text-sm text-muted-foreground">Loading candidates…</p>
          </div>
        </div>
      ) : filteredCandidates.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed bg-muted/20 px-6 py-14 text-center">
          <div className="mb-4 rounded-full bg-violet-100 p-4 dark:bg-violet-950/40">
            <Upload className="h-8 w-8 text-violet-600" />
          </div>
          <h3 className="text-lg font-semibold">No candidates found</h3>
          <p className="mt-1 max-w-md text-sm text-muted-foreground">
            {searchTerm
              ? "No profiles match your search. Try a different keyword."
              : "Upload resumes to build your talent pool and run agentic job matching."}
          </p>
          {!searchTerm && (
            <Button className="mt-5" onClick={() => setShowUpload(true)}>
              <Upload className="mr-2 h-4 w-4" />
              Upload first resume
            </Button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredCandidates.map((candidate) => (
            <CandidateCard
              key={candidate.id}
              candidate={candidate}
              onDelete={handleDeleteCandidate}
            />
          ))}
        </div>
      )}

      <ConfirmDeleteDialog
        open={!!candidateToDelete}
        onOpenChange={(open) => !open && setCandidateToDelete(null)}
        title={`Remove "${candidateToDelete?.name || 'Candidate'}"?`}
        description="Their resume will be hidden and removed from QuantChat and matching. This cannot be undone."
        warningNote={
          (candidateToDelete?.active_applications ?? 0) > 0
            ? `Note: This candidate currently has ${candidateToDelete?.active_applications} active application(s).`
            : undefined
        }
        confirmLabel="Remove Candidate"
        cancelLabel="Cancel"
        onConfirm={executeDeleteCandidate}
        isDeleting={isDeleting}
      />
    </div>
  );
}
