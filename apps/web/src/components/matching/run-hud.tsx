"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  FastForward,
  Gauge,
  Globe2,
  ScanSearch,
  ShieldAlert,
  Sparkles,
  Timer,
  WifiOff,
} from "lucide-react";

import { cn } from "@/lib/utils";
import type { RunSignals, StreamStatus } from "./use-match-stream";

interface RunHudProps {
  status: StreamStatus;
  elapsedMs: number;
  sinceLastEventMs: number;
  currentLayer: 1 | 2 | 3 | 4 | null;
  signals: RunSignals;
  totalThoughts: number;
  className?: string;
}

const LAYERS: { layer: 1 | 2 | 3 | 4; label: string; tone: string }[] = [
  { layer: 1, label: "Pre-flight", tone: "from-slate-300 to-slate-400" },
  { layer: 2, label: "Specialist Swarm", tone: "from-emerald-400 to-emerald-500" },
  { layer: 3, label: "Debate", tone: "from-amber-400 to-amber-500" },
  { layer: 4, label: "Insights", tone: "from-violet-400 to-violet-500" },
];

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const mm = Math.floor(s / 60).toString().padStart(2, "0");
  const ss = (s % 60).toString().padStart(2, "0");
  const tenths = Math.floor((ms % 1000) / 100);
  return `${mm}:${ss}.${tenths}`;
}

/**
 * Live HUD shown above the swarm visualiser + thoughts stream.
 *
 * Production must-haves it adds vs. the previous "running…" badge:
 *   - Big, monospaced elapsed timer (recruiters notice when a run is slow).
 *   - 4-step layer progress so the user always knows what stage we're in.
 *   - Stall indicator when no event has arrived for >10s (network or agent
 *     hung; helps support triage tickets).
 *   - Signal banners for every short-circuit / degraded path the orchestrator
 *     can take.  These were INVISIBLE in the previous UI even though the
 *     backend reports them — a major audit gap.
 */
export function RunHud({
  status,
  elapsedMs,
  sinceLastEventMs,
  currentLayer,
  signals,
  totalThoughts,
  className,
}: RunHudProps) {
  // The timer + ticker animations rely on `status === "running"`.  Use a
  // local copy so we don't churn the parent on every frame.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (status !== "running" && status !== "connecting" && status !== "reconnecting") return;
    const id = window.setInterval(() => setTick((n) => (n + 1) % 1000), 200);
    return () => window.clearInterval(id);
  }, [status]);

  const stalled = status === "running" && sinceLastEventMs > 10_000;
  const reconnecting = status === "reconnecting";

  return (
    <div
      role="region"
      aria-label="Live match run status"
      className={cn(
        "rounded-xl border bg-gradient-to-br from-card via-card to-card/80",
        "shadow-sm overflow-hidden",
        className,
      )}
    >
      {/* Top row: timer + status badge + counter */}
      <div className="flex flex-wrap items-center gap-3 px-4 py-3 border-b">
        <div className="flex items-center gap-2 min-w-[160px]">
          <Timer
            className={cn(
              "h-4 w-4",
              status === "running" ? "text-emerald-500" : "text-muted-foreground",
            )}
          />
          <span
            className="font-mono text-lg tracking-tight tabular-nums"
            aria-live="polite"
            aria-atomic="true"
          >
            {formatElapsed(elapsedMs)}
          </span>
          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
            elapsed
          </span>
          {/* hidden span to keep React rendering on tick — avoids stutter */}
          <span className="sr-only">{tick}</span>
        </div>

        <StatusPill status={status} stalled={stalled} reconnecting={reconnecting} />

        <div className="ml-auto flex items-center gap-1.5 text-xs text-muted-foreground font-mono">
          <Activity className="h-3.5 w-3.5" />
          <span>{totalThoughts} events</span>
        </div>
      </div>

      {/* Middle row: layer progress */}
      <div className="px-4 py-3 grid grid-cols-4 gap-2">
        {LAYERS.map((l) => {
          const reached = currentLayer !== null && currentLayer >= l.layer;
          const active = currentLayer === l.layer && status === "running";
          return (
            <div key={l.layer} className="flex flex-col gap-1">
              <div
                className={cn(
                  "h-1.5 rounded-full transition-all",
                  reached
                    ? `bg-gradient-to-r ${l.tone}`
                    : "bg-muted",
                  active && "animate-pulse shadow-sm",
                )}
              />
              <div className="flex items-baseline justify-between text-[10px]">
                <span
                  className={cn(
                    "uppercase tracking-wider font-semibold",
                    reached ? "text-foreground" : "text-muted-foreground",
                  )}
                >
                  L{l.layer} · {l.label}
                </span>
                {active && (
                  <span className="text-emerald-600 font-mono">●</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Bottom row: signal banners (only render if at least one signal is on) */}
      {(signals.cacheHit ||
        signals.fastPath ||
        signals.criticSkipped ||
        signals.criticDisabled ||
        signals.fallbacks.length > 0 ||
        signals.jdHygiene !== undefined ||
        signals.groundedness !== undefined ||
        signals.locationFit !== undefined ||
        stalled ||
        reconnecting) && (
        <div className="border-t bg-muted/20 px-4 py-2 flex flex-wrap items-center gap-2">
          {/* JD hygiene comes first — it's a JD-level signal and the highest-priority one */}
          {signals.jdHygiene && signals.jdHygiene.severity !== "ok" && (
            <Banner
              tone={signals.jdHygiene.severity === "block" ? "warn" : "info"}
              icon={ShieldAlert}
              title={`JD hygiene · ${signals.jdHygiene.severity.toUpperCase()}`}
              detail={
                signals.jdHygiene.summary ||
                `${signals.jdHygiene.issueCount} issue(s) detected on this JD.`
              }
            />
          )}
          {/* Location fit — second highest-priority (often a hard filter) */}
          {signals.locationFit && signals.locationFit.fit !== "ok" && (() => {
            const lf = signals.locationFit;
            const tone: "ok" | "warn" | "info" =
              lf.fit === "block" ? "warn" : lf.fit === "warn" ? "warn" : "info";
            const title =
              lf.fit === "block"
                ? "Location fit · BLOCK"
                : lf.fit === "warn"
                  ? lf.requiresRelocation
                    ? "Location · relocation required"
                    : "Location · review"
                  : "Location · unknown";
            return (
              <Banner
                tone={tone}
                icon={Globe2}
                title={title}
                detail={
                  lf.summary ||
                  (lf.fit === "block"
                    ? "Country / region mismatch and role is not remote."
                    : "Recruiter should verify location compatibility.")
                }
              />
            );
          })()}
          {/* Groundedness — second highest-priority signal */}
          {signals.groundedness && (() => {
            const g = signals.groundedness;
            if (!g.rawTextAvailable) {
              return (
                <Banner
                  key="g"
                  tone="info"
                  icon={ScanSearch}
                  title="Groundedness · skipped"
                  detail="No raw resume / JD text available — verifier could not run."
                />
              );
            }
            const pct = Math.round(g.overallPct * 100);
            const tone: "ok" | "warn" | "info" =
              pct >= 90 ? "ok" : pct >= 60 ? "info" : "warn";
            const detail =
              g.fabricated > 0
                ? `${pct}% of evidence verified · ${g.fabricated} fabricated quote(s) stripped.`
                : `${pct}% of evidence verified (${g.total} quote${g.total === 1 ? "" : "s"} checked).`;
            return (
              <Banner
                key="g"
                tone={tone}
                icon={ScanSearch}
                title={`Groundedness · ${pct}%`}
                detail={detail}
              />
            );
          })()}
          {signals.cacheHit && (
            <Banner
              tone="info"
              icon={Database}
              title="Cache hit"
              detail="Result served from previously computed run."
            />
          )}
          {signals.fastPath === "reject" && (
            <Banner
              tone="warn"
              icon={FastForward}
              title="Fast-path reject"
              detail="Embedding similarity below the reject threshold — full swarm skipped."
            />
          )}
          {signals.fastPath === "strong_hire" && (
            <Banner
              tone="ok"
              icon={FastForward}
              title="Fast-path strong-hire"
              detail="Embedding similarity above the strong-hire threshold — full swarm skipped."
            />
          )}
          {signals.criticSkipped && (
            <Banner
              tone="info"
              icon={Sparkles}
              title="Critic skipped"
              detail={
                signals.debateRoundsExecuted !== undefined
                  ? `High-confidence consensus after ${signals.debateRoundsExecuted} round(s).`
                  : "High-confidence consensus from the swarm."
              }
            />
          )}
          {signals.criticDisabled && (
            <Banner
              tone="warn"
              icon={AlertTriangle}
              title="Critic disabled"
              detail="Configuration disabled the critic — review with caution."
            />
          )}
          {signals.fallbacks.length > 0 && (
            <Banner
              tone="warn"
              icon={ShieldAlert}
              title={`${signals.fallbacks.length} fallback${signals.fallbacks.length > 1 ? "s" : ""}`}
              detail={signals.fallbacks.join(", ")}
            />
          )}
          {stalled && (
            <Banner
              tone="warn"
              icon={Gauge}
              title="No new events for 10s+"
              detail="The swarm may be waiting on Vertex — confirm before retrying."
            />
          )}
          {reconnecting && (
            <Banner
              tone="info"
              icon={WifiOff}
              title="Reconnecting…"
              detail="The SSE stream dropped; we're attempting one resume."
            />
          )}
          {/* swarm-health summary (post-run) */}
          {signals.swarmHealth && (
            <Banner
              tone={signals.swarmHealth.all_specialists_real_scores ? "ok" : "warn"}
              icon={CheckCircle2}
              title="Swarm health"
              detail={
                signals.swarmHealth.all_specialists_real_scores
                  ? `${signals.swarmHealth.specialist_count ?? 0} specialists fully scored`
                  : `${signals.swarmHealth.specialists_neutral_fallback ?? 0}/${signals.swarmHealth.specialist_count ?? 0} on fallback`
              }
            />
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function StatusPill({
  status,
  stalled,
  reconnecting,
}: {
  status: StreamStatus;
  stalled: boolean;
  reconnecting: boolean;
}) {
  const label = stalled
    ? "stalled"
    : reconnecting
      ? "reconnecting"
      : status;
  const tone =
    status === "running"
      ? stalled
        ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300"
        : "bg-emerald-100 text-emerald-800 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300"
      : status === "error"
        ? "bg-red-100 text-red-800 border-red-300 dark:bg-red-950 dark:text-red-300"
        : status === "done"
          ? "bg-violet-100 text-violet-800 border-violet-300 dark:bg-violet-950 dark:text-violet-300"
          : status === "reconnecting"
            ? "bg-amber-100 text-amber-800 border-amber-300 dark:bg-amber-950 dark:text-amber-300"
            : "bg-muted text-muted-foreground border-border";

  return (
    <span
      className={cn(
        "text-[10px] font-bold uppercase tracking-wider rounded-full px-2.5 py-1 border",
        tone,
      )}
    >
      {(status === "running" || reconnecting) && !stalled && (
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-current mr-1 animate-pulse align-middle" />
      )}
      {stalled && (
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-amber-500 mr-1 align-middle" />
      )}
      {label}
    </span>
  );
}

function Banner({
  tone,
  icon: Icon,
  title,
  detail,
}: {
  tone: "ok" | "info" | "warn";
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  detail: string;
}) {
  const tones = {
    ok: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200",
    info: "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-800 dark:bg-sky-950/40 dark:text-sky-200",
    warn: "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200",
  } as const;
  return (
    <div
      role="status"
      className={cn(
        "flex items-center gap-2 rounded-md border px-2.5 py-1 text-xs",
        tones[tone],
      )}
    >
      <Icon className="h-3.5 w-3.5 shrink-0" />
      <span className="font-semibold">{title}</span>
      <span className="text-[11px] opacity-80 truncate max-w-[280px]" title={detail}>
        · {detail}
      </span>
    </div>
  );
}
