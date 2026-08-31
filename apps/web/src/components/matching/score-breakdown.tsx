"use client";

import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

interface DimensionScore {
  dimension: string;
  score: number;
  confidence?: number;
  summary?: string;
  strengths?: string[];
  gaps?: string[];
  agent_name?: string;
}

const DIMENSION_LABELS: Record<string, string> = {
  skills: "Skills & Tooling",
  experience: "Experience & Seniority",
  education: "Education & Certifications",
  domain: "Domain & Industry",
  culture: "Culture & Soft Skills",
  growth: "Growth Trajectory",
  projects: "Projects & Delivery",
  risk: "Risk Assessment",
};

const scoreColor = (score: number) => {
  if (score >= 80) return "from-emerald-500 to-emerald-400";
  if (score >= 65) return "from-emerald-400 to-amber-400";
  if (score >= 45) return "from-amber-400 to-orange-400";
  return "from-orange-400 to-red-500";
};

interface ScoreBreakdownProps {
  scores: DimensionScore[];
  riskScore?: { score: number; summary?: string; flag_count?: number };
  className?: string;
}

export function ScoreBreakdown({ scores, riskScore, className }: ScoreBreakdownProps) {
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      {scores.map((s) => (
        <DimensionRow key={s.dimension} score={s} />
      ))}
      {riskScore && (
        <DimensionRow
          score={{
            dimension: "risk",
            score: riskScore.score,
            summary: riskScore.summary,
            agent_name: "RiskAgent",
          }}
        />
      )}
    </div>
  );
}

function DimensionRow({ score }: { score: DimensionScore }) {
  const [expanded, setExpanded] = useState(false);
  const label = DIMENSION_LABELS[score.dimension] ?? score.dimension;

  return (
    <div className="rounded-lg border border-slate-200/80 bg-card shadow-sm overflow-hidden dark:border-slate-800">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full px-4 py-3 flex items-center gap-4 hover:bg-muted/30 transition-colors text-left"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-sm font-semibold truncate">{label}</span>
            <div className="flex items-baseline gap-2">
              {score.confidence !== undefined && (
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
                  conf {Math.round(score.confidence * 100)}%
                </span>
              )}
              <span className="text-base font-bold tabular-nums">
                {Math.round(score.score)}
                <span className="text-xs text-muted-foreground font-normal">/100</span>
              </span>
            </div>
          </div>
          <div className="mt-1.5 relative">
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className={cn(
                  "h-full rounded-full bg-gradient-to-r transition-all duration-500",
                  scoreColor(score.score),
                )}
                style={{ width: `${Math.max(2, Math.min(100, score.score))}%` }}
              />
            </div>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />
        ) : (
          <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
        )}
      </button>
      {expanded && (
        <div className="border-t bg-muted/20 px-4 py-3 space-y-3 text-sm">
          {score.summary && (
            <p className="text-foreground/80 leading-relaxed">{score.summary}</p>
          )}
          {(score.strengths?.length ?? 0) > 0 && (
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 mb-1">
                Strengths
              </div>
              <ul className="space-y-1">
                {score.strengths!.map((s, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-emerald-500 shrink-0">•</span>
                    <span className="text-sm">{s}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(score.gaps?.length ?? 0) > 0 && (
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-orange-700 dark:text-orange-400 mb-1">
                Gaps
              </div>
              <ul className="space-y-1">
                {score.gaps!.map((g, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-orange-500 shrink-0">•</span>
                    <span className="text-sm">{g}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {score.agent_name && (
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground font-mono pt-1">
              {score.agent_name}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
