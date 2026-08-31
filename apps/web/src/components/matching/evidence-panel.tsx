"use client";

import { Quote, Search, FileText, User } from "lucide-react";

import { cn } from "@/lib/utils";

interface Evidence {
  source: "resume" | "jd";
  quote: string;
  relevance?: number;
  note?: string | null;
}

interface ExplanationCard {
  dimension: string;
  contribution_pct: number;
  why_score: string;
  evidence?: Evidence[];
}

interface ExplainabilityReport {
  cards?: ExplanationCard[];
  decision_drivers?: string[];
  counterfactual?: string | null;
  quality_warning?: string | null;
}

const DIMENSION_LABELS: Record<string, string> = {
  skills: "Skills",
  experience: "Experience",
  education: "Education",
  domain: "Domain",
  culture: "Culture",
  growth: "Growth",
  risk: "Risk",
};

interface EvidencePanelProps {
  report: ExplainabilityReport;
  className?: string;
}

export function EvidencePanel({ report, className }: EvidencePanelProps) {
  const cards = report.cards ?? [];

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      {report.quality_warning ? (
        <div
          role="status"
          className="rounded-xl border-2 border-amber-400/80 bg-amber-50 dark:bg-amber-950/40 dark:border-amber-600 p-4 text-sm text-amber-950 dark:text-amber-100"
        >
          <div className="text-xs font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300 mb-2">
            Degraded run — read before interpreting scores
          </div>
          <p className="leading-relaxed">{report.quality_warning}</p>
        </div>
      ) : null}

      {(report.decision_drivers?.length ?? 0) > 0 && (
        <div className="rounded-xl border bg-card p-4">
          <div className="flex items-center gap-2 mb-2">
            <Search className="h-4 w-4 text-violet-600" />
            <h4 className="text-sm font-semibold">Decision Drivers</h4>
          </div>
          <ul className="space-y-1 text-sm">
            {report.decision_drivers!.map((d, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-violet-500 font-bold shrink-0">{i + 1}.</span>
                <span>{d}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {report.counterfactual && (
        <div className="rounded-xl border-2 border-dashed border-violet-300 dark:border-violet-700 bg-violet-50/50 dark:bg-violet-950/20 p-4">
          <div className="text-[10px] font-bold uppercase tracking-wider text-violet-700 dark:text-violet-400 mb-1">
            Counterfactual — what would push them to the next tier?
          </div>
          <p className="text-sm">{report.counterfactual}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {cards.map((card) => (
          <DimensionCard key={card.dimension} card={card} />
        ))}
      </div>
    </div>
  );
}

function DimensionCard({ card }: { card: ExplanationCard }) {
  const positive = card.contribution_pct >= 0;
  const label = DIMENSION_LABELS[card.dimension] ?? card.dimension;

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="flex items-center justify-between border-b px-3 py-2">
        <h5 className="text-sm font-semibold">{label}</h5>
        <span
          className={cn(
            "rounded px-2 py-0.5 text-xs font-bold tabular-nums",
            positive
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
              : "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
          )}
        >
          {positive ? "+" : ""}
          {card.contribution_pct.toFixed(1)} pts
        </span>
      </div>
      <div className="px-3 py-2.5 space-y-2">
        <p className="text-xs leading-relaxed text-foreground/80">
          {card.why_score}
        </p>
        {(card.evidence?.length ?? 0) > 0 && (
          <div className="space-y-1.5">
            {card.evidence!.map((ev, i) => (
              <EvidenceQuote key={i} evidence={ev} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EvidenceQuote({ evidence }: { evidence: Evidence }) {
  const Icon = evidence.source === "resume" ? User : FileText;
  const colorClass =
    evidence.source === "resume"
      ? "border-l-sky-400 bg-sky-50/50 dark:bg-sky-950/20"
      : "border-l-amber-400 bg-amber-50/50 dark:bg-amber-950/20";

  return (
    <div
      className={cn(
        "rounded border-l-2 px-2 py-1.5 text-xs",
        colorClass,
      )}
    >
      <div className="flex items-center gap-1 text-[9px] uppercase tracking-wider text-muted-foreground font-mono mb-0.5">
        <Icon className="h-2.5 w-2.5" />
        <span>{evidence.source}</span>
        {evidence.relevance !== undefined && (
          <span className="ml-auto">{Math.round(evidence.relevance * 100)}%</span>
        )}
      </div>
      <p className="italic flex gap-1">
        <Quote className="h-3 w-3 shrink-0 text-muted-foreground mt-0.5" />
        <span className="leading-snug">{evidence.quote}</span>
      </p>
      {evidence.note && (
        <p className="text-[10px] text-muted-foreground mt-1">{evidence.note}</p>
      )}
    </div>
  );
}
