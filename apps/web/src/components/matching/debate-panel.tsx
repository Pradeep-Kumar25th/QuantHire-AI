"use client";

import { Brain, MessageSquareWarning, Gavel } from "lucide-react";

import { cn } from "@/lib/utils";

interface SynthesisResult {
  overall_score: number;
  summary?: string;
  top_strengths?: string[];
  top_gaps?: string[];
}

interface CriticChallenge {
  is_overall_score_justified: boolean;
  blind_spots?: string[];
  counter_arguments?: string[];
  suggested_score_adjustment?: number;
  summary?: string;
}

interface ArbitratorResult {
  final_score: number;
  verdict: string;
  rationale?: string;
  accepted_critic_points?: string[];
  rejected_critic_points?: string[];
}

interface DebatePanelProps {
  synthesis?: SynthesisResult;
  critic?: CriticChallenge | null;
  arbitrator?: ArbitratorResult;
  className?: string;
}

export function DebatePanel({
  synthesis,
  critic,
  arbitrator,
  className,
}: DebatePanelProps) {
  return (
    <div className={cn("flex flex-col gap-3", className)}>
      {synthesis && (
        <DebateCard
          icon={Brain}
          title="Synthesizer"
          subtitle={`Overall ${synthesis.overall_score.toFixed(1)} / 100`}
          tone="indigo"
        >
          {synthesis.summary && (
            <p className="text-sm leading-relaxed mb-2">{synthesis.summary}</p>
          )}
          {(synthesis.top_strengths?.length ?? 0) > 0 && (
            <div className="mt-2">
              <Label color="emerald">Top Strengths</Label>
              <BulletList items={synthesis.top_strengths!} accent="emerald" />
            </div>
          )}
          {(synthesis.top_gaps?.length ?? 0) > 0 && (
            <div className="mt-2">
              <Label color="orange">Top Gaps</Label>
              <BulletList items={synthesis.top_gaps!} accent="orange" />
            </div>
          )}
        </DebateCard>
      )}

      {critic && (
        <DebateCard
          icon={MessageSquareWarning}
          title="Critic"
          subtitle={
            critic.is_overall_score_justified
              ? "Verdict accepted"
              : `Suggested adj. ${critic.suggested_score_adjustment !== undefined ? (critic.suggested_score_adjustment >= 0 ? "+" : "") + critic.suggested_score_adjustment.toFixed(1) : ""}`
          }
          tone="amber"
        >
          {critic.summary && (
            <p className="text-sm leading-relaxed mb-2">{critic.summary}</p>
          )}
          {(critic.blind_spots?.length ?? 0) > 0 && (
            <div className="mt-2">
              <Label color="amber">Blind Spots Identified</Label>
              <BulletList items={critic.blind_spots!} accent="amber" />
            </div>
          )}
          {(critic.counter_arguments?.length ?? 0) > 0 && (
            <div className="mt-2">
              <Label color="orange">Counter-arguments</Label>
              <BulletList items={critic.counter_arguments!} accent="orange" />
            </div>
          )}
        </DebateCard>
      )}

      {arbitrator && (
        <DebateCard
          icon={Gavel}
          title="Arbitrator"
          subtitle={`Final: ${arbitrator.final_score.toFixed(1)} / 100`}
          tone="violet"
        >
          {arbitrator.rationale && (
            <p className="text-sm leading-relaxed mb-2">{arbitrator.rationale}</p>
          )}
          {(arbitrator.accepted_critic_points?.length ?? 0) > 0 && (
            <div className="mt-2">
              <Label color="emerald">Accepted Critic Points</Label>
              <BulletList items={arbitrator.accepted_critic_points!} accent="emerald" />
            </div>
          )}
          {(arbitrator.rejected_critic_points?.length ?? 0) > 0 && (
            <div className="mt-2">
              <Label color="orange">Rejected Critic Points</Label>
              <BulletList items={arbitrator.rejected_critic_points!} accent="orange" />
            </div>
          )}
        </DebateCard>
      )}
    </div>
  );
}

const TONE_CLASS: Record<string, string> = {
  indigo: "border-l-4 border-l-indigo-500",
  amber: "border-l-4 border-l-amber-500",
  violet: "border-l-4 border-l-violet-500",
};

function DebateCard({
  icon: Icon,
  title,
  subtitle,
  tone,
  children,
}: {
  icon: any;
  title: string;
  subtitle?: string;
  tone: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("rounded-xl border bg-card", TONE_CLASS[tone])}>
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <h4 className="text-sm font-semibold">{title}</h4>
        {subtitle && (
          <span className="ml-auto text-xs font-mono tabular-nums text-muted-foreground">
            {subtitle}
          </span>
        )}
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  );
}

function Label({ children, color }: { children: React.ReactNode; color: string }) {
  const colors: Record<string, string> = {
    emerald: "text-emerald-700 dark:text-emerald-400",
    amber: "text-amber-700 dark:text-amber-400",
    orange: "text-orange-700 dark:text-orange-400",
    violet: "text-violet-700 dark:text-violet-400",
  };
  return (
    <div
      className={cn(
        "text-[10px] font-bold uppercase tracking-wider mb-1",
        colors[color],
      )}
    >
      {children}
    </div>
  );
}

function BulletList({
  items,
  accent,
}: {
  items: string[];
  accent: "emerald" | "amber" | "orange" | "violet";
}) {
  const colors: Record<string, string> = {
    emerald: "text-emerald-500",
    amber: "text-amber-500",
    orange: "text-orange-500",
    violet: "text-violet-500",
  };
  return (
    <ul className="space-y-1 text-sm">
      {items.map((s, i) => (
        <li key={i} className="flex gap-2">
          <span className={cn("shrink-0", colors[accent])}>•</span>
          <span>{s}</span>
        </li>
      ))}
    </ul>
  );
}
