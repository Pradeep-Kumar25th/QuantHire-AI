"use client";

import { AlertTriangle, ShieldCheck, ShieldAlert, Scale } from "lucide-react";

import { cn } from "@/lib/utils";

interface RiskFlag {
  category: string;
  severity: "low" | "medium" | "high" | string;
  description: string;
  evidence?: string;
}

interface RiskAssessment {
  score: number;
  flags?: RiskFlag[];
  summary?: string;
}

const SEVERITY_STYLE: Record<string, string> = {
  high: "border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-950/30",
  medium: "border-amber-300 bg-amber-50 dark:border-amber-800 dark:bg-amber-950/30",
  low: "border-slate-300 bg-slate-50 dark:border-slate-700 dark:bg-slate-900/30",
};

const SEVERITY_LABEL: Record<string, string> = {
  high: "text-red-700 dark:text-red-400",
  medium: "text-amber-700 dark:text-amber-400",
  low: "text-slate-700 dark:text-slate-400",
};

interface RiskCardProps {
  risk?: RiskAssessment | null;
  className?: string;
}

export function RiskCard({ risk, className }: RiskCardProps) {
  if (!risk) return null;
  const flags = risk.flags ?? [];
  const noFlags = flags.length === 0;
  const Icon = noFlags ? ShieldCheck : ShieldAlert;
  const tone = noFlags ? "text-emerald-600" : "text-orange-600";

  return (
    <div className={cn("rounded-xl border bg-card", className)}>
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <Icon className={cn("h-4 w-4", tone)} />
        <h4 className="text-sm font-semibold">Risk & Red Flags</h4>
        <span className="ml-auto text-xs font-mono tabular-nums">
          {Math.round(risk.score)}/100 clean
        </span>
      </div>
      <div className="px-4 py-3 space-y-2">
        {risk.summary && (
          <p className="text-sm text-foreground/80 leading-relaxed">{risk.summary}</p>
        )}
        {noFlags ? (
          <div className="text-sm text-emerald-700 dark:text-emerald-400 font-medium flex items-center gap-1.5">
            <ShieldCheck className="h-4 w-4" />
            No red flags identified.
          </div>
        ) : (
          <div className="space-y-2">
            {flags.map((flag, i) => (
              <div
                key={i}
                className={cn(
                  "rounded border-l-4 px-3 py-2",
                  SEVERITY_STYLE[flag.severity?.toLowerCase()] ?? SEVERITY_STYLE.low,
                )}
              >
                <div className="flex items-baseline gap-2 mb-0.5">
                  <AlertTriangle
                    className={cn(
                      "h-3.5 w-3.5",
                      SEVERITY_LABEL[flag.severity?.toLowerCase()] ?? "text-muted-foreground",
                    )}
                  />
                  <span className="text-xs font-bold uppercase tracking-wider">
                    {flag.category}
                  </span>
                  <span
                    className={cn(
                      "text-[10px] font-bold uppercase",
                      SEVERITY_LABEL[flag.severity?.toLowerCase()] ?? "text-muted-foreground",
                    )}
                  >
                    · {flag.severity}
                  </span>
                </div>
                <p className="text-sm">{flag.description}</p>
                {flag.evidence && (
                  <p className="text-xs italic text-muted-foreground mt-1">
                    “{flag.evidence}”
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

interface BiasAudit {
  is_fair: boolean;
  issues?: string[];
  mitigations?: string[];
  summary?: string;
}

interface BiasCardProps {
  audit?: BiasAudit | null;
  className?: string;
}

export function BiasCard({ audit, className }: BiasCardProps) {
  if (!audit) return null;
  const tone = audit.is_fair ? "text-emerald-600" : "text-orange-600";

  return (
    <div className={cn("rounded-xl border bg-card", className)}>
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <Scale className={cn("h-4 w-4", tone)} />
        <h4 className="text-sm font-semibold">Bias & Fairness Audit</h4>
        <span
          className={cn(
            "ml-auto text-[10px] font-bold uppercase tracking-wider rounded px-2 py-0.5",
            audit.is_fair
              ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
              : "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-300",
          )}
        >
          {audit.is_fair ? "Fair" : "Concerns"}
        </span>
      </div>
      <div className="px-4 py-3 space-y-2">
        {audit.summary && (
          <p className="text-sm text-foreground/80 leading-relaxed">{audit.summary}</p>
        )}
        {(audit.issues?.length ?? 0) > 0 && (
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-orange-700 dark:text-orange-400 mb-1">
              Issues
            </div>
            <ul className="space-y-1 text-sm">
              {audit.issues!.map((s, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-orange-500 shrink-0">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        {(audit.mitigations?.length ?? 0) > 0 && (
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400 mb-1">
              Mitigations
            </div>
            <ul className="space-y-1 text-sm">
              {audit.mitigations!.map((s, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-emerald-500 shrink-0">•</span>
                  <span>{s}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
