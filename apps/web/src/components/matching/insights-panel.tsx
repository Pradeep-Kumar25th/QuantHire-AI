"use client";

import { Lightbulb, MessageCircleQuestion, ListChecks, ArrowRightCircle, Briefcase } from "lucide-react";

import { cn } from "@/lib/utils";

interface InterviewQuestion {
  question: string;
  category?: string;
  rationale?: string;
  targets_dimension?: string | null;
}

interface HRInsights {
  decision_tip?: string;
  key_talking_points?: string[];
  interview_questions?: InterviewQuestion[];
  recommended_next_steps?: string[];
  salary_band_hint?: string | null;
  onboarding_focus_areas?: string[];
}

const CATEGORY_COLOR: Record<string, string> = {
  technical: "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300",
  behavioural: "bg-violet-100 text-violet-800 dark:bg-violet-950 dark:text-violet-300",
  experience: "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300",
  scenario: "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300",
  culture: "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300",
  leadership: "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300",
};

interface InsightsPanelProps {
  insights: HRInsights;
  className?: string;
}

export function InsightsPanel({ insights, className }: InsightsPanelProps) {
  const tip = insights.decision_tip;
  const talking = insights.key_talking_points ?? [];
  const questions = insights.interview_questions ?? [];
  const nextSteps = insights.recommended_next_steps ?? [];
  const onboarding = insights.onboarding_focus_areas ?? [];

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      {tip && (
        <div className="rounded-xl border-2 border-amber-300 dark:border-amber-700 bg-gradient-to-br from-amber-50 to-amber-100/50 dark:from-amber-950/40 dark:to-amber-900/20 p-4">
          <div className="flex items-start gap-3">
            <Lightbulb className="h-5 w-5 text-amber-600 dark:text-amber-400 mt-0.5 shrink-0" />
            <div>
              <div className="text-[10px] font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300">
                HR Advisor
              </div>
              <div className="text-base font-semibold text-amber-950 dark:text-amber-100 mt-0.5">
                {tip}
              </div>
              {insights.salary_band_hint && (
                <div className="text-sm text-amber-900 dark:text-amber-200 mt-1.5 flex items-center gap-1.5">
                  <Briefcase className="h-3.5 w-3.5" />
                  {insights.salary_band_hint}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {talking.length > 0 && (
        <Card icon={ListChecks} title="Key Talking Points" tone="indigo">
          <ul className="space-y-2 text-sm">
            {talking.map((t, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-indigo-500 font-bold shrink-0">{i + 1}.</span>
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {questions.length > 0 && (
        <Card icon={MessageCircleQuestion} title="Suggested Interview Questions" tone="emerald">
          <div className="space-y-3">
            {questions.map((q, i) => (
              <div
                key={i}
                className="rounded-lg border bg-background/50 p-3"
              >
                <div className="flex flex-wrap items-start gap-2 mb-1.5">
                  {q.category && (
                    <span
                      className={cn(
                        "inline-block rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider",
                        CATEGORY_COLOR[q.category.toLowerCase()] ??
                          "bg-muted text-muted-foreground",
                      )}
                    >
                      {q.category}
                    </span>
                  )}
                  {q.targets_dimension && (
                    <span className="text-[9px] font-mono uppercase text-muted-foreground">
                      ↳ targets {q.targets_dimension}
                    </span>
                  )}
                </div>
                <p className="text-sm font-medium leading-snug">{q.question}</p>
                {q.rationale && (
                  <p className="text-xs text-muted-foreground italic mt-1.5">
                    {q.rationale}
                  </p>
                )}
              </div>
            ))}
          </div>
        </Card>
      )}

      {nextSteps.length > 0 && (
        <Card icon={ArrowRightCircle} title="Recommended Next Steps" tone="violet">
          <ol className="space-y-1.5 text-sm list-decimal list-inside">
            {nextSteps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </Card>
      )}

      {onboarding.length > 0 && (
        <Card icon={Briefcase} title="Onboarding Focus Areas" tone="sky">
          <div className="flex flex-wrap gap-1.5">
            {onboarding.map((o, i) => (
              <span
                key={i}
                className="inline-block rounded-full bg-sky-100 dark:bg-sky-950 text-sky-900 dark:text-sky-300 px-2.5 py-0.5 text-xs"
              >
                {o}
              </span>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}

const TONE_CLASSES: Record<string, string> = {
  indigo: "border-l-4 border-l-indigo-500",
  emerald: "border-l-4 border-l-emerald-500",
  violet: "border-l-4 border-l-violet-500",
  sky: "border-l-4 border-l-sky-500",
};

function Card({
  icon: Icon,
  title,
  tone,
  children,
}: {
  icon: any;
  title: string;
  tone: string;
  children: React.ReactNode;
}) {
  return (
    <div className={cn("rounded-xl border bg-card", TONE_CLASSES[tone])}>
      <div className="flex items-center gap-2 border-b px-4 py-2.5">
        <Icon className="h-4 w-4 text-muted-foreground" />
        <h4 className="text-sm font-semibold">{title}</h4>
      </div>
      <div className="px-4 py-3">{children}</div>
    </div>
  );
}
