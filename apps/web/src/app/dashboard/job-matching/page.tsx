"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  Target,
  Sparkles,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  Loader2,
  Settings2,
  BarChart3,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import {
  MatchLauncher,
  type CandidateOption,
  type JDOption,
} from "@/components/matching/match-launcher";
import { SwarmVisualizer } from "@/components/matching/swarm-visualizer";
import { AgentThoughtsStream } from "@/components/matching/agent-thoughts-stream";
import { MatchResultView } from "@/components/matching/match-result-view";
import { RunHud } from "@/components/matching/run-hud";
import { useMatchStream } from "@/components/matching/use-match-stream";

type Stage = "setup" | "running" | "results";

interface ActiveMatch {
  candidate: CandidateOption;
  jd: JDOption;
  weights?: Record<string, number>;
}

const STAGES: { id: Stage; label: string; icon: typeof Settings2 }[] = [
  { id: "setup", label: "Configure", icon: Settings2 },
  { id: "running", label: "Swarm run", icon: Loader2 },
  { id: "results", label: "Results", icon: BarChart3 },
];

function StageStepper({ stage }: { stage: Stage }) {
  const order: Stage[] = ["setup", "running", "results"];
  const currentIndex = order.indexOf(stage);

  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-muted/20 px-3 py-2">
      {STAGES.map((item, index) => {
        const Icon = item.icon;
        const isActive = item.id === stage;
        const isComplete = index < currentIndex;
        return (
          <div key={item.id} className="flex items-center gap-2">
            {index > 0 && (
              <div
                className={cn(
                  "hidden sm:block h-px w-8",
                  isComplete ? "bg-emerald-400" : "bg-border",
                )}
              />
            )}
            <div
              className={cn(
                "flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium transition-colors",
                isActive &&
                  "bg-emerald-600 text-white shadow-sm shadow-emerald-600/20",
                isComplete && !isActive && "bg-emerald-50 text-emerald-700",
                !isActive && !isComplete && "text-muted-foreground",
              )}
            >
              {isComplete && !isActive ? (
                <CheckCircle2 className="h-3.5 w-3.5" />
              ) : (
                <Icon
                  className={cn(
                    "h-3.5 w-3.5",
                    item.id === "running" && isActive && "animate-spin",
                  )}
                />
              )}
              {item.label}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function JobMatchingPageContent() {
  const searchParams = useSearchParams();
  const preselectedCandidateId = searchParams.get("candidateId");

  const [stage, setStage] = useState<Stage>("setup");
  const [active, setActive] = useState<ActiveMatch | null>(null);
  const [focusedAgent, setFocusedAgent] = useState<string | null>(null);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [showRunLog, setShowRunLog] = useState(true);
  const resultsRef = useRef<HTMLDivElement>(null);

  const stream = useMatchStream();

  const handleLaunch = useCallback(
    (args: { candidate: CandidateOption; jd: JDOption; weights?: Record<string, number> }) => {
      setActive(args);
      setStage("running");
      setFocusedAgent(null);
      setRunStartedAt(Date.now());
      setShowRunLog(true);
      stream.start({
        candidate_id: args.candidate.candidate_id,
        jd_id: args.jd.jd_id,
        weights: args.weights,
      });
    },
    [stream],
  );

  const handleReset = useCallback(() => {
    stream.reset();
    setStage("setup");
    setActive(null);
    setFocusedAgent(null);
    setRunStartedAt(null);
    setShowRunLog(true);
  }, [stream]);

  const handleRunAgain = useCallback(() => {
    if (!active) return;
    setStage("running");
    setFocusedAgent(null);
    setRunStartedAt(Date.now());
    setShowRunLog(true);
    stream.start({
      candidate_id: active.candidate.candidate_id,
      jd_id: active.jd.jd_id,
      weights: active.weights,
    });
  }, [active, stream]);

  useEffect(() => {
    if (
      stage === "running" &&
      stream.result &&
      (stream.status === "done" || stream.status === "idle")
    ) {
      setStage("results");
      setShowRunLog(false);
    }
  }, [stage, stream.result, stream.status]);

  const scrollToResults = useCallback(() => {
    const el = resultsRef.current;
    if (!el) return;
    const top = el.getBoundingClientRect().top + window.scrollY - 88;
    window.scrollTo({ top: Math.max(0, top), behavior: "smooth" });
  }, []);

  useEffect(() => {
    if (stage !== "results" || !stream.result) return;
    requestAnimationFrame(() => scrollToResults());
  }, [stage, stream.result, scrollToResults]);

  const showLivePanels =
    stage === "running" || (stage === "results" && showRunLog);

  const liveMonitorHeight =
    stage === "results" ? "h-[min(620px,70vh)]" : "h-[min(780px,82vh)]";

  useEffect(() => {
    if (stage !== "running") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleReset();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [stage, handleReset]);

  const activeStrip = useMemo(() => {
    if (!active) return null;
    return (
      <div className="rounded-xl border bg-card px-4 py-3 flex flex-wrap items-center gap-3 shadow-sm">
        <Sparkles className="h-4 w-4 text-emerald-500 shrink-0" />
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm min-w-0 flex-1">
          <span className="font-semibold truncate max-w-[200px]">
            {active.candidate.name}
          </span>
          <span className="text-muted-foreground">→</span>
          <span className="font-semibold truncate max-w-[260px]">
            {active.jd.job_title}
          </span>
          {active.jd.department && (
            <span className="text-xs text-muted-foreground">
              ({active.jd.department})
            </span>
          )}
        </div>
        {stage === "results" && (
          <Button variant="outline" size="sm" onClick={scrollToResults}>
            Jump to scores
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={handleReset}
          aria-label="Cancel run (Esc)"
          title="Cancel run (Esc)"
        >
          {stage === "running" ? "Cancel" : "New match"}
        </Button>
      </div>
    );
  }, [active, handleReset, scrollToResults, stage]);

  return (
    <div className="w-full min-w-0 px-3 py-4 sm:px-5 lg:px-6 lg:py-5 space-y-4">
      {/* HEADER */}
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-start gap-3 min-w-0 flex-1">
          <div className="rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 p-2 shadow-md shadow-emerald-500/20 shrink-0">
            <Target className="h-5 w-5 text-white" />
          </div>
          <div className="min-w-0">
            <h1 className="text-xl sm:text-2xl font-bold tracking-tight flex flex-wrap items-center gap-2">
              Job Matching
              <span className="text-[10px] sm:text-xs font-mono text-emerald-700 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-300 px-2 py-0.5 rounded-full">
                Agentic Swarm · v1
              </span>
            </h1>
            <p className="text-xs sm:text-sm text-muted-foreground mt-0.5 line-clamp-2 sm:line-clamp-none">
              13-agent hierarchical swarm · evidence-backed scoring
            </p>
          </div>
        </div>
        <StageStepper stage={stage} />
      </div>

      {stage === "setup" && (
        <MatchLauncher
          onLaunch={handleLaunch}
          disabled={stream.status === "running"}
          initialCandidateId={preselectedCandidateId}
        />
      )}

      {(stage === "running" || stage === "results") && active && (
        <div className="space-y-4">
          {activeStrip}

          {/* Results first — no scrolling past the swarm to see scores */}
          {stage === "results" && stream.result && (
            <div
              ref={resultsRef}
              id="match-results"
              className="scroll-mt-20 w-full min-w-0"
            >
              <MatchResultView
                result={stream.result}
                candidateName={active.candidate.name}
                jobTitle={active.jd.job_title}
                onReset={handleReset}
                onRunAgain={handleRunAgain}
              />
            </div>
          )}

          {stream.status === "error" && (
            <div
              role="alert"
              className="rounded-lg border-2 border-red-300 bg-red-50 dark:bg-red-950/30 px-4 py-3 flex items-start gap-2 text-sm"
            >
              <AlertCircle className="h-5 w-5 text-red-600 shrink-0" />
              <div className="flex-1">
                <div className="font-semibold text-red-900 dark:text-red-300">
                  Swarm encountered an error
                </div>
                <div className="text-red-800 dark:text-red-400">{stream.error}</div>
                <Button
                  variant="outline"
                  size="sm"
                  className="mt-3"
                  onClick={handleRunAgain}
                >
                  Retry
                </Button>
              </div>
            </div>
          )}

          {stage === "running" &&
            (stream.status === "running" || stream.status === "connecting") &&
            stream.thoughts.length === 0 && (
              <div className="rounded-xl border bg-muted/20 px-6 py-10 text-center text-sm text-muted-foreground">
                <Sparkles className="h-6 w-6 text-emerald-500 mx-auto mb-2 animate-pulse" />
                Spinning up the HSS-D specialist swarm…
              </div>
            )}

          {/* Live run log — full height while running, compact + collapsible after results */}
          {(showLivePanels || stage === "results") && (
            <div className="rounded-xl border bg-card overflow-hidden">
              <button
                type="button"
                onClick={() => setShowRunLog((value) => !value)}
                className="w-full flex items-center justify-between gap-3 px-4 py-3 hover:bg-muted/30 transition-colors text-left"
              >
                <div>
                  <div className="text-sm font-semibold">
                    {stage === "running" ? "Live swarm monitor" : "Agent run log"}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {stage === "running"
                      ? "Watch agents score dimensions in real time."
                      : showRunLog
                        ? "Thought stream and swarm graph from this evaluation."
                        : "Collapsed — expand to review how agents reached the score."}
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {stream.thoughts.length > 0 && (
                    <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                      {stream.thoughts.length} events
                    </span>
                  )}
                  {stage === "results" &&
                    (showRunLog ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ))}
                </div>
              </button>

              {showLivePanels && (
                <div className="border-t border-slate-200/70 p-3 sm:p-4 dark:border-slate-800">
                  {(stage === "running" || stream.thoughts.length > 0) && (
                    <RunHud
                      status={stream.status}
                      elapsedMs={stream.elapsedMs}
                      sinceLastEventMs={stream.sinceLastEventMs}
                      currentLayer={stream.currentLayer}
                      signals={stream.signals}
                      totalThoughts={stream.thoughts.length}
                    />
                  )}

                  {stream.thoughts.length > 0 && (
                    <div
                      className={cn(
                        "grid grid-cols-1 lg:grid-cols-2 gap-4 w-full min-w-0 items-stretch mt-3 overflow-hidden",
                        liveMonitorHeight,
                      )}
                    >
                      <SwarmVisualizer
                        thoughts={stream.thoughts}
                        agents={stream.agents}
                        result={stream.result}
                        focusedAgent={focusedAgent}
                        onFocusAgent={setFocusedAgent}
                        startedAt={runStartedAt}
                        compact={stage === "results"}
                        fillHeight
                        className="min-h-[480px] h-full w-full min-w-0 overflow-hidden"
                      />
                      <AgentThoughtsStream
                        thoughts={stream.thoughts}
                        focusedAgent={focusedAgent}
                        onClearFocus={() => setFocusedAgent(null)}
                        startedAt={runStartedAt}
                        fillHeight
                        className="min-h-[480px] h-full w-full min-w-0 overflow-hidden"
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function JobMatchingPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center p-8 text-sm text-muted-foreground">
          Loading job matching…
        </div>
      }
    >
      <JobMatchingPageContent />
    </Suspense>
  );
}
