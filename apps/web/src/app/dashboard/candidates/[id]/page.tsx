"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, Loader2, RefreshCw, UserX } from "lucide-react";
import { isAxiosError } from "axios";

import { CandidateProfileView } from "@/components/candidates/candidate-profile-view";
import { Button } from "@/components/ui/button";
import { useCandidate } from "@/hooks/use-candidates";
import { mapCandidateDetail } from "@/lib/candidate-mapper";
import { getApiErrorMessage } from "@/lib/api-errors";

export default function CandidateDetailPage() {
  const params = useParams();
  const candidateId = String(params.id ?? "").trim();
  const { data, isLoading, isError, error, refetch, isFetching } = useCandidate(candidateId);

  if (!candidateId || candidateId === "undefined") {
    return (
      <div className="mx-auto flex min-h-[50vh] max-w-lg flex-col items-center justify-center gap-4 p-8 text-center">
        <UserX className="h-10 w-10 text-muted-foreground" />
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">Invalid candidate link</h2>
          <p className="text-sm text-muted-foreground">
            This profile URL is missing a candidate id.
          </p>
        </div>
        <Button asChild>
          <Link href="/dashboard/candidates">Back to candidates</Link>
        </Button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] flex-col items-center justify-center gap-3 p-8 text-muted-foreground">
        <Loader2 className="h-8 w-8 animate-spin text-[#437A8B]" />
        <p className="text-sm">Loading candidate profile…</p>
      </div>
    );
  }

  if (isError || !data) {
    const message = getApiErrorMessage(error, "Unable to load this candidate.");
    const isNotFound =
      (isAxiosError(error) && error.response?.status === 404) ||
      message.toLowerCase().includes("not found");

    return (
      <div className="mx-auto flex min-h-[50vh] max-w-lg flex-col items-center justify-center gap-4 p-8 text-center">
        <div className="rounded-full bg-red-50 p-3 dark:bg-red-950/30">
          {isNotFound ? (
            <UserX className="h-8 w-8 text-red-600" />
          ) : (
            <AlertCircle className="h-8 w-8 text-red-600" />
          )}
        </div>
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">
            {isNotFound ? "Candidate not found" : "Failed to load profile"}
          </h2>
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
        <div className="flex flex-wrap justify-center gap-2">
          <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={isFetching ? "mr-2 h-4 w-4 animate-spin" : "mr-2 h-4 w-4"} />
            Retry
          </Button>
          <Button asChild>
            <Link href="/dashboard/candidates">Back to candidates</Link>
          </Button>
        </div>
      </div>
    );
  }

  const candidate = mapCandidateDetail(data as unknown as Record<string, unknown>);

  if (!candidate.id) {
    return (
      <div className="mx-auto flex min-h-[50vh] max-w-lg flex-col items-center justify-center gap-4 p-8 text-center">
        <AlertCircle className="h-10 w-10 text-red-600" />
        <div className="space-y-1">
          <h2 className="text-lg font-semibold">Profile data incomplete</h2>
          <p className="text-sm text-muted-foreground">
            The server response did not include a valid candidate id.
          </p>
        </div>
        <Button asChild>
          <Link href="/dashboard/candidates">Back to candidates</Link>
        </Button>
      </div>
    );
  }

  return <CandidateProfileView candidate={candidate} />;
}
