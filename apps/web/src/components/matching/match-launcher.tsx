"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  User,
  Briefcase,
  Sparkles,
  RefreshCw,
  AlertCircle,
  ArrowRight,
  SlidersHorizontal,
  X,
} from "lucide-react";

import { api } from "@/lib/api";
import { getApiErrorMessage } from "@/lib/api-errors";
import { mapCandidateDetail, type CandidateDetail } from "@/lib/candidate-mapper";
import { AZURE_HSS_HINT, AZURE_MATCHING_DATA_HINT } from "@/lib/azure-messages";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";

export interface CandidateOption {
  candidate_id: string;
  name: string;
  email?: string;
  headline?: string;
  total_years_experience?: number;
  skills?: string[];
  location?: string;
}

export interface JDOption {
  jd_id: string;
  job_title: string;
  department?: string;
  location?: string;
  job_level?: string;
  required_skills?: string[];
  summary?: string;
}

interface MatchLauncherProps {
  onLaunch: (args: {
    candidate: CandidateOption;
    jd: JDOption;
    weights?: Record<string, number>;
  }) => void;
  disabled?: boolean;
  initialCandidateId?: string | null;
}

const DIMENSIONS = [
  { key: "skills", label: "Skills" },
  { key: "experience", label: "Experience" },
  { key: "education", label: "Education" },
  { key: "domain", label: "Domain" },
  { key: "culture", label: "Culture" },
  { key: "growth", label: "Growth" },
  { key: "projects", label: "Projects" },
  { key: "risk", label: "Risk" },
];

const DEFAULT_WEIGHTS: Record<string, number> = {
  skills: 0.26,
  experience: 0.18,
  education: 0.08,
  domain: 0.13,
  culture: 0.09,
  growth: 0.09,
  projects: 0.12,
  risk: 0.05,
};

function formatSkillChips(values?: string[]): string[] | undefined {
  if (!values?.length) return undefined;
  const cleaned = values
    .map((value) => value.trim())
    .filter(
      (value) =>
        value.length > 0 &&
        value.length <= 36 &&
        !/^(education|experience|required|preferred|technical skills)\s*:/i.test(value),
    )
    .slice(0, 3);
  return cleaned.length ? cleaned : undefined;
}

function jdRowSubtitle(jd: JDOption): string {
  if (jd.summary?.trim()) {
    return jd.summary.trim();
  }
  return [jd.department, jd.location, jd.job_level].filter(Boolean).join(" · ");
}

function candidateOptionFromDetail(mapped: CandidateDetail): CandidateOption {
  return {
    candidate_id: mapped.id,
    name: mapped.name,
    email: mapped.displayEmail ?? mapped.email,
    headline: mapped.headline ?? undefined,
    total_years_experience: mapped.experienceYears,
    skills: mapped.skillNames,
    location: mapped.location,
  };
}

export function MatchLauncher({ onLaunch, disabled, initialCandidateId }: MatchLauncherProps) {
  const [candidates, setCandidates] = useState<CandidateOption[]>([]);
  const [jds, setJDs] = useState<JDOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [candidateSearch, setCandidateSearch] = useState("");
  const [jdSearch, setJDSearch] = useState("");
  const [selectedCandidate, setSelectedCandidate] = useState<CandidateOption | null>(null);
  const [selectedJD, setSelectedJD] = useState<JDOption | null>(null);

  const [weights, setWeights] = useState<Record<string, number>>(DEFAULT_WEIGHTS);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [matchingReady, setMatchingReady] = useState<boolean | null>(null);
  const [matchingMessage, setMatchingMessage] = useState<string | null>(null);
  const [preselectResolved, setPreselectResolved] = useState(false);
  const preselectFetchedRef = useRef(false);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    try {
      const [cRes, jRes] = await Promise.all([
        api.jobMatching.listCandidates(),
        api.jobMatching.listJDs(),
      ]);
      setCandidates((cRes.data?.candidates ?? []) as CandidateOption[]);
      setJDs((jRes.data?.jds ?? []) as JDOption[]);
    } catch (err: unknown) {
      console.error("Failed to load matching data:", err);
      setError(getApiErrorMessage(err, "Failed to load candidates and JDs."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  useEffect(() => {
    preselectFetchedRef.current = false;
    setPreselectResolved(false);
  }, [initialCandidateId]);

  useEffect(() => {
    if (!initialCandidateId || loading) return;

    const match = candidates.find((c) => c.candidate_id === initialCandidateId);
    if (match) {
      setSelectedCandidate(match);
      setPreselectResolved(true);
      return;
    }

    if (preselectFetchedRef.current) {
      setPreselectResolved(true);
      return;
    }
    preselectFetchedRef.current = true;

    let cancelled = false;
    (async () => {
      try {
        const response = await api.candidates.get(initialCandidateId);
        if (cancelled) return;
        const mapped = mapCandidateDetail(response.data as Record<string, unknown>);
        if (!mapped.id) return;
        const option = candidateOptionFromDetail(mapped);
        setSelectedCandidate(option);
        setCandidates((prev) => {
          if (prev.some((c) => c.candidate_id === option.candidate_id)) return prev;
          return [option, ...prev];
        });
      } catch {
        // Profile missing or API error — banner below explains next steps.
      } finally {
        if (!cancelled) setPreselectResolved(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [initialCandidateId, candidates, loading]);

  useEffect(() => {
    const checkMatchingReady = async () => {
      try {
        const { testJobMatchingReady } = await import("@/lib/api-health");
        const result = await testJobMatchingReady();
        setMatchingReady(result.success);
        setMatchingMessage(result.success ? null : result.message);
      } catch (err) {
        setMatchingReady(false);
        setMatchingMessage(
          err instanceof Error ? err.message : "Unable to verify HSS-D readiness",
        );
      }
    };
    void checkMatchingReady();
  }, []);

  const filteredCandidates = useMemo(() => {
    const q = candidateSearch.trim().toLowerCase();
    if (!q) return candidates;
    return candidates.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.email?.toLowerCase().includes(q) ||
        c.headline?.toLowerCase().includes(q) ||
        c.skills?.some((s) => s.toLowerCase().includes(q)),
    );
  }, [candidates, candidateSearch]);

  const filteredJDs = useMemo(() => {
    const q = jdSearch.trim().toLowerCase();
    if (!q) return jds;
    return jds.filter(
      (j) =>
        j.job_title.toLowerCase().includes(q) ||
        j.department?.toLowerCase().includes(q) ||
        j.required_skills?.some((s) => s.toLowerCase().includes(q)),
    );
  }, [jds, jdSearch]);

  const ready =
    !!selectedCandidate && !!selectedJD && !disabled && matchingReady !== false;

  const preselectMissing =
    Boolean(initialCandidateId) &&
    preselectResolved &&
    !loading &&
    !selectedCandidate;

  const preselectedFromProfile =
    Boolean(initialCandidateId) &&
    selectedCandidate?.candidate_id === initialCandidateId;

  const handleLaunch = () => {
    if (!selectedCandidate || !selectedJD) return;
    const customised = Object.entries(weights).some(
      ([k, v]) => Math.abs(v - DEFAULT_WEIGHTS[k]) > 0.01,
    );
    onLaunch({
      candidate: selectedCandidate,
      jd: selectedJD,
      weights: customised ? weights : undefined,
    });
  };

  const updateWeight = (key: string, value: number) => {
    setWeights((prev) => ({ ...prev, [key]: value }));
  };

  return (
    <div className="rounded-2xl border bg-card shadow-sm overflow-hidden">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b bg-gradient-to-r from-emerald-50/60 via-background to-amber-50/40 dark:from-emerald-950/20 dark:to-amber-950/10 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Configure Match</h2>
          <p className="text-xs text-muted-foreground mt-0.5">
            Pick one candidate and one JD side by side, then launch the swarm.
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {!loading && (
            <span className="hidden sm:inline text-xs text-muted-foreground">
              {candidates.length} candidates · {jds.length} JDs
            </span>
          )}
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            <RefreshCw className={cn("h-4 w-4 mr-1.5", loading && "animate-spin")} />
            Refresh
          </Button>
        </div>
      </div>

      {matchingReady === false && matchingMessage && (
        <AlertBanner tone="warn" title="HSS-D swarm not ready" message={matchingMessage} hint={AZURE_HSS_HINT} />
      )}

      {error && (
        <AlertBanner tone="error" title="Could not load data" message={error} hint={AZURE_MATCHING_DATA_HINT} />
      )}

      {preselectedFromProfile && selectedCandidate && (
        <div className="mx-4 mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-900 dark:border-emerald-900/40 dark:bg-emerald-950/30 dark:text-emerald-100">
          Pre-selected from candidate profile:{" "}
          <span className="font-semibold">{selectedCandidate.name}</span>. Choose a job
          description below, then launch the agentic match.
        </div>
      )}

      {preselectMissing && (
        <AlertBanner
          tone="warn"
          title="Candidate not indexed for matching yet"
          message="This profile exists, but it is not in the job-matching vector store yet. Refresh after indexing completes, or pick the candidate manually below."
        />
      )}

      {/* Side-by-side selection — always 2 columns from sm breakpoint up */}
      <div className="relative grid grid-cols-1 sm:grid-cols-2 min-h-[420px]">
        <SelectionPanel
          title="Candidate"
          icon={User}
          tone="sky"
          count={filteredCandidates.length}
          searchValue={candidateSearch}
          onSearchChange={setCandidateSearch}
          searchPlaceholder="Search name, skill, headline…"
          loading={loading}
          empty={
            !loading &&
            candidates.length === 0 &&
            "No resumes yet. Upload in Candidates first."
          }
          selectedLabel={selectedCandidate?.name}
          onClearSelection={() => setSelectedCandidate(null)}
        >
          {filteredCandidates.map((c) => (
            <SelectionRow
              key={c.candidate_id}
              selected={selectedCandidate?.candidate_id === c.candidate_id}
              onClick={() => setSelectedCandidate(c)}
              title={c.name}
              subtitle={c.headline || c.email || c.location || ""}
              meta={
                c.total_years_experience
                  ? `${c.total_years_experience} yrs`
                  : undefined
              }
              chips={formatSkillChips(c.skills)}
            />
          ))}
        </SelectionPanel>

        <div
          className="hidden sm:flex absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 h-9 w-9 items-center justify-center rounded-full border bg-background shadow-md text-emerald-600"
          aria-hidden
        >
          <ArrowRight className="h-4 w-4" />
        </div>

        <SelectionPanel
          title="Job Description"
          icon={Briefcase}
          tone="amber"
          count={filteredJDs.length}
          searchValue={jdSearch}
          onSearchChange={setJDSearch}
          searchPlaceholder="Search title, department, skill…"
          loading={loading}
          empty={
            !loading &&
            jds.length === 0 &&
            "No JDs yet. Generate one in Jobs → AI Generate JD."
          }
          selectedLabel={selectedJD?.job_title}
          onClearSelection={() => setSelectedJD(null)}
          className="border-t sm:border-t-0 sm:border-l"
        >
          {filteredJDs.map((j) => (
            <SelectionRow
              key={j.jd_id}
              selected={selectedJD?.jd_id === j.jd_id}
              onClick={() => setSelectedJD(j)}
              title={j.job_title}
              subtitle={jdRowSubtitle(j)}
              meta={j.job_level}
              chips={formatSkillChips(j.required_skills)}
            />
          ))}
        </SelectionPanel>
      </div>

      {/* Advanced weights — compact collapsible */}
      <div className="border-t">
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          className="w-full px-4 py-2.5 flex items-center justify-between hover:bg-muted/30 transition-colors text-left text-sm"
        >
          <span className="flex items-center gap-2 font-medium">
            <SlidersHorizontal className="h-4 w-4 text-muted-foreground" />
            Ensemble weights (optional)
          </span>
          <span className="text-xs uppercase tracking-wider text-muted-foreground">
            {showAdvanced ? "Hide" : "Show"}
          </span>
        </button>
        {showAdvanced && (
          <div className="border-t px-4 py-3 grid grid-cols-2 lg:grid-cols-4 gap-3 bg-muted/10">
            {DIMENSIONS.map((d) => (
              <label key={d.key} className="text-xs space-y-1 block">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{d.label}</span>
                  <span className="font-mono tabular-nums text-muted-foreground">
                    {Math.round(weights[d.key] * 100)}%
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={weights[d.key] ?? 0}
                  onChange={(e) => updateWeight(d.key, Number(e.target.value))}
                  className="w-full accent-emerald-500"
                />
              </label>
            ))}
            <div className="col-span-2 lg:col-span-4 flex items-center justify-between text-[11px] text-muted-foreground border-t pt-2">
              <span>Weights auto-normalise to 1.0 inside the swarm.</span>
              <button
                type="button"
                onClick={() => setWeights(DEFAULT_WEIGHTS)}
                className="text-emerald-600 hover:underline"
              >
                Reset defaults
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Launch bar */}
      <div className="border-t bg-muted/30 px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-wrap items-center gap-2 min-w-0 flex-1">
            {selectedCandidate ? (
              <Badge variant="secondary" className="gap-1 max-w-[200px] truncate">
                <User className="h-3 w-3 shrink-0" />
                {selectedCandidate.name}
                <button
                  type="button"
                  onClick={() => setSelectedCandidate(null)}
                  className="ml-1 rounded-full hover:bg-muted p-0.5"
                  aria-label="Clear candidate"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ) : (
              <span className="text-xs text-muted-foreground">No candidate selected</span>
            )}
            <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            {selectedJD ? (
              <Badge variant="secondary" className="gap-1 max-w-[220px] truncate">
                <Briefcase className="h-3 w-3 shrink-0" />
                {selectedJD.job_title}
                <button
                  type="button"
                  onClick={() => setSelectedJD(null)}
                  className="ml-1 rounded-full hover:bg-muted p-0.5"
                  aria-label="Clear job description"
                >
                  <X className="h-3 w-3" />
                </button>
              </Badge>
            ) : (
              <span className="text-xs text-muted-foreground">No JD selected</span>
            )}
          </div>
          <Button
            onClick={handleLaunch}
            disabled={!ready}
            size="lg"
            className="min-w-[168px] shrink-0"
          >
            <Sparkles className="h-4 w-4 mr-2" />
            Launch Swarm
          </Button>
        </div>
      </div>
    </div>
  );
}

function AlertBanner({
  tone,
  title,
  message,
  hint,
}: {
  tone: "warn" | "error";
  title: string;
  message: string;
  hint?: string;
}) {
  const styles =
    tone === "warn"
      ? "border-amber-200 bg-amber-50 dark:bg-amber-950/30"
      : "border-red-200 bg-red-50 dark:bg-red-950/30";
  const iconColor = tone === "warn" ? "text-amber-700" : "text-red-600";
  return (
    <div className={cn("border-b px-4 py-3 flex items-start gap-2 text-sm", styles)}>
      <AlertCircle className={cn("h-4 w-4 shrink-0 mt-0.5", iconColor)} />
      <div>
        <div className="font-semibold">{title}</div>
        <div className="text-muted-foreground">{message}</div>
        {hint && <div className="text-xs text-muted-foreground mt-1">{hint}</div>}
      </div>
    </div>
  );
}

function SelectionPanel({
  title,
  icon: Icon,
  tone,
  count,
  searchValue,
  onSearchChange,
  searchPlaceholder,
  empty,
  loading,
  selectedLabel,
  onClearSelection,
  className,
  children,
}: {
  title: string;
  icon: typeof User;
  tone: "sky" | "amber";
  count?: number;
  searchValue: string;
  onSearchChange: (v: string) => void;
  searchPlaceholder: string;
  empty?: string | false;
  loading: boolean;
  selectedLabel?: string;
  onClearSelection?: () => void;
  className?: string;
  children: React.ReactNode;
}) {
  const headerTone =
    tone === "sky"
      ? "bg-sky-50/80 dark:bg-sky-950/20 text-sky-900 dark:text-sky-100"
      : "bg-amber-50/80 dark:bg-amber-950/20 text-amber-900 dark:text-amber-100";

  return (
    <div className={cn("flex flex-col min-h-[420px] h-full", className)}>
      <div
        className={cn(
          "flex items-center justify-between gap-2 border-b px-3 py-2",
          headerTone,
        )}
      >
        <div className="flex items-center gap-2 min-w-0">
          <Icon className="h-4 w-4 shrink-0 opacity-70" />
          <h3 className="text-sm font-semibold truncate">{title}</h3>
          {typeof count === "number" && (
            <Badge variant="outline" className="text-[10px] h-5 px-1.5 shrink-0">
              {count}
            </Badge>
          )}
        </div>
        {selectedLabel && onClearSelection && (
          <button
            type="button"
            onClick={onClearSelection}
            className="text-[10px] font-medium uppercase tracking-wide opacity-70 hover:opacity-100 shrink-0"
          >
            Clear
          </button>
        )}
      </div>

      <div className="flex flex-col flex-1 min-h-0 p-3 gap-2">
        <div className="relative shrink-0">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={searchValue}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={searchPlaceholder}
            className="pl-8 h-8 text-sm"
          />
        </div>

        <ScrollArea className="flex-1 min-h-[280px] max-h-[min(420px,45vh)] pr-1">
          <div className="space-y-1.5 pr-2">
            {loading ? (
              <div className="text-xs text-muted-foreground py-12 text-center">Loading…</div>
            ) : empty ? (
              <div className="text-xs text-muted-foreground py-12 text-center px-2">{empty}</div>
            ) : (
              children
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

function SelectionRow({
  selected,
  onClick,
  title,
  subtitle,
  meta,
  chips,
}: {
  selected: boolean;
  onClick: () => void;
  title: string;
  subtitle?: string;
  meta?: string;
  chips?: string[];
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "w-full text-left rounded-lg border px-2.5 py-2 transition-all hover:bg-muted/50",
        selected
          ? "border-emerald-500 bg-emerald-50/80 dark:bg-emerald-950/40 ring-2 ring-emerald-500/30 shadow-sm"
          : "border-border/80 bg-background hover:border-border",
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium text-sm leading-snug line-clamp-2 min-w-0">{title}</div>
        {meta && (
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground font-mono shrink-0 pt-0.5">
            {meta}
          </span>
        )}
      </div>
      {subtitle && (
        <p className="text-xs text-muted-foreground line-clamp-2 mt-1 leading-relaxed">
          {subtitle}
        </p>
      )}
      {(chips?.length ?? 0) > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {chips!.map((chip, index) => (
            <Badge
              key={`${chip}-${index}`}
              variant="secondary"
              className="text-[10px] py-0 h-4 max-w-[100px] truncate font-normal"
              title={chip}
            >
              {chip}
            </Badge>
          ))}
        </div>
      )}
    </button>
  );
}
