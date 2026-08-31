"use client";

import { useMemo } from "react";
import { ArrowLeft, Download, RotateCcw, User, Briefcase } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";

import { ScoreGauge } from "./score-gauge";
import { ScoreRadar } from "./score-radar";
import { ScoreBreakdown } from "./score-breakdown";
import { InsightsPanel } from "./insights-panel";
import { EvidencePanel } from "./evidence-panel";
import { DebatePanel } from "./debate-panel";
import { RiskCard, BiasCard } from "./risk-bias-cards";

interface MatchResultViewProps {
  result: any;
  candidateName: string;
  jobTitle: string;
  onReset: () => void;
  onRunAgain: () => void;
}

export function MatchResultView({
  result,
  candidateName,
  jobTitle,
  onReset,
  onRunAgain,
}: MatchResultViewProps) {
  const dimensionScores = result?.dimension_scores ?? [];
  const radarData = useMemo(() => {
    const data = dimensionScores.map((s: any) => ({
      dimension: s.dimension,
      score: s.score,
    }));
    if (result?.risk?.score !== undefined) {
      data.push({ dimension: "risk", score: result.risk.score });
    }
    return data;
  }, [dimensionScores, result?.risk?.score]);

  const swarmHealthBanner = useMemo(() => {
    const sh = result?.metadata?.swarm_health as
      | {
          all_specialists_real_scores?: boolean;
          specialists_neutral_fallback?: number;
          specialist_count?: number;
          risk_agent_placeholder?: boolean;
          bias_auditor_placeholder?: boolean;
        }
      | undefined;
    if (!sh || sh.all_specialists_real_scores) return null;
    const parts: string[] = [];
    if (
      typeof sh.specialists_neutral_fallback === "number" &&
      typeof sh.specialist_count === "number" &&
      sh.specialist_count > 0
    ) {
      parts.push(
        `${sh.specialists_neutral_fallback}/${sh.specialist_count} specialists used neutral placeholders (check Vertex model and GCP_LOCATION).`,
      );
    }
    if (sh.risk_agent_placeholder)
      parts.push("Risk agent fell back to default.");
    if (sh.bias_auditor_placeholder)
      parts.push("Bias auditor fell back to default.");
    if (parts.length === 0) return null;
    return (
      <div
        role="status"
        className="rounded-xl border-2 border-amber-400/80 bg-amber-50 dark:bg-amber-950/40 dark:border-amber-600 px-4 py-3 text-sm text-amber-950 dark:text-amber-100"
      >
        <div className="text-xs font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300 mb-1">
          Degraded match run
        </div>
        <ul className="list-disc pl-5 space-y-1">
          {parts.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      </div>
    );
  }, [result?.metadata?.swarm_health]);

  const handleExport = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `match-${result?.candidate_id?.slice(0, 8) || "result"}-${result?.jd_id?.slice(0, 8) || "jd"}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5 w-full">
      {/* HEADER */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-4 py-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="ghost" size="sm" onClick={onReset}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            New Match
          </Button>
          <div className="hidden md:block h-4 w-px bg-border" />
          <div className="text-sm text-muted-foreground flex items-center gap-2 min-w-0">
            <User className="h-3.5 w-3.5 shrink-0" />
            <span className="font-semibold text-foreground truncate max-w-[160px]">
              {candidateName}
            </span>
            <span className="opacity-50">→</span>
            <Briefcase className="h-3.5 w-3.5 shrink-0" />
            <span className="font-semibold text-foreground truncate max-w-[220px]">
              {jobTitle}
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={onRunAgain}>
            <RotateCcw className="h-4 w-4 mr-2" />
            Run Again
          </Button>
          <Button variant="outline" size="sm" onClick={handleExport}>
            <Download className="h-4 w-4 mr-2" />
            Export JSON
          </Button>
        </div>
      </div>

      {swarmHealthBanner}

      {/* HERO — gauge + summary */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 w-full">
        <div className="rounded-2xl border bg-gradient-to-br from-card via-card to-emerald-50/30 dark:to-emerald-950/10 p-5 lg:col-span-2 flex flex-col items-center justify-center">
          <ScoreGauge
            score={result?.overall_score ?? 0}
            verdict={result?.verdict}
            confidence={result?.confidence}
            size={220}
          />
        </div>
        <div className="rounded-2xl border bg-card p-5 lg:col-span-3 space-y-3">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">
              Verdict Rationale
            </div>
            <p className="text-base leading-relaxed">
              {result?.arbitrator?.rationale ||
                result?.synthesis?.summary ||
                "Match analysis complete."}
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t">
            {result?.synthesis?.top_strengths?.length > 0 && (
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 mb-1">
                  Top Strengths
                </div>
                <ul className="space-y-1 text-sm">
                  {result.synthesis.top_strengths
                    .slice(0, 4)
                    .map((s: string, i: number) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-emerald-500 shrink-0">•</span>
                        <span>{s}</span>
                      </li>
                    ))}
                </ul>
              </div>
            )}
            {result?.synthesis?.top_gaps?.length > 0 && (
              <div>
                <div className="text-[10px] font-bold uppercase tracking-wider text-orange-700 dark:text-orange-400 mb-1">
                  Top Gaps
                </div>
                <ul className="space-y-1 text-sm">
                  {result.synthesis.top_gaps
                    .slice(0, 4)
                    .map((g: string, i: number) => (
                      <li key={i} className="flex gap-2">
                        <span className="text-orange-500 shrink-0">•</span>
                        <span>{g}</span>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* TABS */}
      <Tabs defaultValue="breakdown" className="w-full">
        <TabsList className="h-auto w-full justify-start gap-1 overflow-x-auto rounded-xl border border-slate-200/80 bg-muted/20 p-1 dark:border-slate-800">
          <TabsTrigger value="breakdown" className="rounded-lg text-xs sm:text-sm">
            Breakdown
          </TabsTrigger>
          <TabsTrigger value="insights" className="rounded-lg text-xs sm:text-sm">
            Insights
          </TabsTrigger>
          <TabsTrigger value="evidence" className="rounded-lg text-xs sm:text-sm">
            Explainability
          </TabsTrigger>
          <TabsTrigger value="debate" className="rounded-lg text-xs sm:text-sm">
            Debate
          </TabsTrigger>
          <TabsTrigger value="risk" className="rounded-lg text-xs sm:text-sm">
            Risk & Fairness
          </TabsTrigger>
        </TabsList>

        <TabsContent value="breakdown" className="mt-4">
          <div className="grid w-full grid-cols-1 gap-4 xl:grid-cols-2">
            <div className="flex min-h-[380px] flex-col rounded-xl border border-slate-200/80 bg-card p-4 shadow-sm dark:border-slate-800">
              <h4 className="mb-1 text-sm font-semibold tracking-tight">
                Dimension radar
              </h4>
              <p className="mb-3 text-xs text-muted-foreground">
                Eight specialist dimensions plus inverted risk score
              </p>
              <div className="flex h-[320px] w-full">
                <ScoreRadar scores={radarData} className="h-full w-full" />
              </div>
            </div>
            <div className="min-w-0 rounded-xl border border-slate-200/80 bg-card p-4 shadow-sm dark:border-slate-800">
              <h4 className="mb-3 text-sm font-semibold tracking-tight">
                Score breakdown
              </h4>
              <ScoreBreakdown
                scores={dimensionScores}
                riskScore={
                  result?.risk
                    ? {
                        score: result.risk.score,
                        summary: result.risk.summary,
                        flag_count: result.risk.flags?.length,
                      }
                    : undefined
                }
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="insights" className="mt-4">
          <InsightsPanel insights={result?.insights ?? {}} />
        </TabsContent>

        <TabsContent value="evidence" className="mt-4">
          <EvidencePanel report={result?.explainability ?? {}} />
        </TabsContent>

        <TabsContent value="debate" className="mt-4">
          <DebatePanel
            synthesis={result?.synthesis}
            critic={result?.critic}
            arbitrator={result?.arbitrator}
          />
        </TabsContent>

        <TabsContent value="risk" className="mt-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <RiskCard risk={result?.risk} />
            <BiasCard audit={result?.bias_audit} />
          </div>
        </TabsContent>
      </Tabs>

      {/* META FOOTER */}
      {result?.metadata && (
        <div className="rounded-lg border bg-muted/20 px-4 py-2.5 text-xs text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 font-mono">
          {result.metadata.elapsed_seconds !== undefined && (
            <span>elapsed: {result.metadata.elapsed_seconds}s</span>
          )}
          {result.metadata.swarm_size !== undefined && (
            <span>swarm: {result.metadata.swarm_size} agents</span>
          )}
          {result.metadata.debate_enabled !== undefined && (
            <span>
              debate: {result.metadata.debate_enabled ? "on" : "off"}
            </span>
          )}
          {result.metadata.bias_audit_enabled !== undefined && (
            <span>
              bias audit: {result.metadata.bias_audit_enabled ? "on" : "off"}
            </span>
          )}
          {result.metadata.run_id && (
            <span className="ml-auto opacity-60">
              run {result.metadata.run_id.slice(0, 8)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
