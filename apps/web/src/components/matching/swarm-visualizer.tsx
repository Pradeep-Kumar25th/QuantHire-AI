"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useMemo, useState } from "react";

import { cn } from "@/lib/utils";
import type { AgentRuntime, AgentThought } from "./use-match-stream";

type AgentNode = {
  id: string;
  label: string;
  layer: 1 | 2 | "2.5" | 3 | 4;
  x: number; // 0..100 within the SVG viewbox
  y: number;
};

const AGENTS: AgentNode[] = [
  // Layer 1 — Pre-flight (3 agents run in parallel via asyncio.gather)
  { id: "Orchestrator", label: "Orchestrator", layer: 1, x: 20, y: 8 },
  { id: "JDHygieneAgent", label: "JD Hygiene", layer: 1, x: 50, y: 8 },
  { id: "LocationFitAgent", label: "Location Fit", layer: 1, x: 80, y: 8 },

  // Layer 2 — Specialist swarm (parallel) — 7 dimension specialists + Risk
  { id: "SkillsAgent", label: "Skills", layer: 2, x: 6, y: 32 },
  { id: "ExperienceAgent", label: "Experience", layer: 2, x: 18, y: 26 },
  { id: "EducationAgent", label: "Education", layer: 2, x: 30, y: 32 },
  { id: "DomainAgent", label: "Domain", layer: 2, x: 42, y: 24 },
  { id: "CultureAgent", label: "Culture", layer: 2, x: 54, y: 32 },
  { id: "GrowthAgent", label: "Growth", layer: 2, x: 66, y: 26 },
  { id: "ProjectsAgent", label: "Projects", layer: 2, x: 80, y: 32 },
  { id: "RiskAgent", label: "Risk", layer: 2, x: 94, y: 26 },

  // Layer 2.5 — Post-swarm audit: deterministic groundedness + LLM bias check
  { id: "EvidenceVerifier", label: "Evidence Check", layer: "2.5", x: 30, y: 50 },
  { id: "BiasAuditor", label: "Bias Audit", layer: "2.5", x: 70, y: 50 },

  // Layer 3 — Debate
  { id: "Synthesizer", label: "Synthesizer", layer: 3, x: 25, y: 70 },
  { id: "Critic", label: "Critic", layer: 3, x: 50, y: 76 },
  { id: "Arbitrator", label: "Arbitrator", layer: 3, x: 75, y: 70 },

  // Layer 4 — Insights
  { id: "HRAdvisor", label: "HR Advisor", layer: 4, x: 32, y: 92 },
  { id: "ExplainabilityAgent", label: "Explainability", layer: 4, x: 68, y: 92 },
];

const SWARM_VIEWBOX = "-6 -8 112 118";

const LAYER_COLORS: Record<string, { stroke: string; fill: string; text: string }> = {
  "1": { stroke: "stroke-slate-400", fill: "fill-slate-100 dark:fill-slate-800", text: "fill-slate-700 dark:fill-slate-200" },
  "2": { stroke: "stroke-emerald-500", fill: "fill-emerald-50 dark:fill-emerald-900/40", text: "fill-emerald-800 dark:fill-emerald-200" },
  "2.5": { stroke: "stroke-cyan-500", fill: "fill-cyan-50 dark:fill-cyan-900/40", text: "fill-cyan-800 dark:fill-cyan-200" },
  "3": { stroke: "stroke-amber-500", fill: "fill-amber-50 dark:fill-amber-900/40", text: "fill-amber-800 dark:fill-amber-200" },
  "4": { stroke: "stroke-violet-500", fill: "fill-violet-50 dark:fill-violet-900/40", text: "fill-violet-800 dark:fill-violet-200" },
};

const STATUS_RING: Record<AgentRuntime["status"], string> = {
  idle: "stroke-slate-300 dark:stroke-slate-700",
  active: "stroke-emerald-500",
  done: "stroke-emerald-600",
  fallback: "stroke-amber-500",
  skipped: "stroke-sky-500",
  error: "stroke-red-500",
};

/** Shared enterprise panel chrome for matching live views. */
const PANEL_SHELL =
  "rounded-xl border border-slate-200/80 bg-card shadow-sm dark:border-slate-800";

interface SwarmVisualizerProps {
  thoughts: AgentThought[];
  agents: Record<string, AgentRuntime>;
  className?: string;
  compact?: boolean;
  /** Stretch to parent flex height instead of a fixed SVG height. */
  fillHeight?: boolean;
  result?: any;
  focusedAgent?: string | null;
  onFocusAgent?: (agent: string | null) => void;
  /** Run start time (epoch ms) for the latency-since-start tooltip. */
  startedAt?: number | null;
}

export function SwarmVisualizer({
  thoughts: _thoughts,
  agents,
  className,
  compact = false,
  fillHeight = false,
  result,
  focusedAgent,
  onFocusAgent,
  startedAt,
}: SwarmVisualizerProps) {
  const [hoverId, setHoverId] = useState<string | null>(null);

  // ---- derive debate phase activity (animates Synth↔Critic↔Arb edges) ----
  const debateActivity = useMemo(() => {
    const synth = agents["Synthesizer"];
    const critic = agents["Critic"];
    const arb = agents["Arbitrator"];
    return {
      synthActive: synth?.status === "active",
      criticActive: critic?.status === "active",
      arbActive: arb?.status === "active",
      anyDebate:
        synth?.status === "active" ||
        critic?.status === "active" ||
        arb?.status === "active",
    };
  }, [agents]);

  // If we have a final result, treat every agent as "done" (modulo fallbacks).
  const isFullyDone = !!result;

  const hovered = hoverId ? agents[hoverId] : null;
  const hoveredNode = hoverId ? AGENTS.find((a) => a.id === hoverId) : null;

  return (
    <div
      className={cn(
        PANEL_SHELL,
        "relative flex flex-col min-h-0 w-full bg-gradient-to-br from-slate-50/80 via-card to-card",
        "dark:from-slate-950 dark:via-slate-950 dark:to-slate-900",
        compact ? "p-3" : "p-4",
        fillHeight && "h-full overflow-hidden",
        className,
      )}
    >
      <div className="mb-3 shrink-0 border-b border-slate-200/70 pb-3 dark:border-slate-800">
        <h3 className="text-sm font-semibold tracking-tight text-foreground">
          Swarm topology
        </h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Click an agent to filter the reasoning stream · hover for score details
        </p>
      </div>

      <div
        className={cn(
          "relative flex min-h-0 w-full flex-1 items-center justify-center overflow-hidden rounded-lg border border-slate-200/70 bg-white/70 dark:border-slate-800 dark:bg-slate-950/40",
          fillHeight ? "min-h-[340px]" : compact ? "h-[320px]" : "h-[400px]",
        )}
      >
        <svg
          viewBox={SWARM_VIEWBOX}
          className="h-full w-full max-h-full p-1"
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Job matching agentic swarm visualisation"
        >
        <defs>
          <pattern
            id="swarm-grid"
            width="8"
            height="8"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 8 0 L 0 0 0 8"
              fill="none"
              className="stroke-slate-200/60 dark:stroke-slate-800/80"
              strokeWidth="0.15"
            />
          </pattern>
          <marker
            id="arrow"
            viewBox="0 0 8 8"
            refX="6"
            refY="4"
            markerWidth="3"
            markerHeight="3"
            orient="auto-start-reverse"
          >
            <path d="M0,0 L8,4 L0,8 z" className="fill-amber-500" />
          </marker>
        </defs>

        <rect
          x="-6"
          y="-8"
          width="112"
          height="118"
          fill="url(#swarm-grid)"
          className="opacity-40"
        />

        {/* Static connection edges (low contrast, base layer) */}
        <g className="opacity-25">
          {/* Orchestrator → Layer 2 */}
          {AGENTS.filter((a) => a.layer === 2).map((agent) => (
            <line
              key={`l1-${agent.id}`}
              x1={50}
              y1={8}
              x2={agent.x}
              y2={agent.y}
              strokeWidth={0.15}
              className="stroke-emerald-400"
            />
          ))}
          {/* Layer 2 → Bias Auditor */}
          {AGENTS.filter((a) => a.layer === 2).map((agent) => (
            <line
              key={`l2-bias-${agent.id}`}
              x1={agent.x}
              y1={agent.y}
              x2={50}
              y2={50}
              strokeWidth={0.1}
              className="stroke-cyan-400"
            />
          ))}
          {/* Bias Auditor → Synthesizer */}
          <line x1={50} y1={50} x2={25} y2={70} strokeWidth={0.2} className="stroke-amber-400" />
          {/* Layer 2 → Synthesizer (direct) */}
          {AGENTS.filter((a) => a.layer === 2).map((agent) => (
            <line
              key={`l2-synth-${agent.id}`}
              x1={agent.x}
              y1={agent.y}
              x2={25}
              y2={70}
              strokeWidth={0.08}
              className="stroke-amber-400"
            />
          ))}
          {/* Arbitrator → Insights */}
          <line x1={75} y1={70} x2={32} y2={92} strokeWidth={0.2} className="stroke-violet-400" />
          <line x1={75} y1={70} x2={68} y2={92} strokeWidth={0.2} className="stroke-violet-400" />
        </g>

        {/* Debate-loop edges (animated when active) */}
        <g>
          <DebateEdge
            from={[25, 70]}
            to={[50, 76]}
            active={debateActivity.synthActive || debateActivity.criticActive}
          />
          <DebateEdge
            from={[50, 76]}
            to={[75, 70]}
            active={debateActivity.criticActive || debateActivity.arbActive}
          />
          {/* Critic → Synthesizer (revision arrow, dotted) */}
          <line
            x1={50}
            y1={76}
            x2={25}
            y2={70}
            strokeWidth={0.18}
            strokeDasharray="0.6 0.6"
            className={cn(
              "stroke-amber-500 transition-opacity",
              debateActivity.criticActive ? "opacity-80" : "opacity-25",
            )}
            markerEnd="url(#arrow)"
          />
        </g>

        {/* Animated traffic flow Orchestrator → active L2 specialists */}
        <AnimatePresence>
          {AGENTS.filter(
            (a) => a.layer === 2 && agents[a.id]?.status === "active",
          ).map((agent) => (
            <motion.circle
              key={`flow-${agent.id}`}
              r={0.5}
              className="fill-emerald-500"
              initial={{ cx: 50, cy: 8, opacity: 0 }}
              animate={{ cx: agent.x, cy: agent.y, opacity: [0, 1, 0] }}
              exit={{ opacity: 0 }}
              transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
            />
          ))}
        </AnimatePresence>

        {/* Agent nodes */}
        {AGENTS.map((agent) => {
          const runtime = agents[agent.id];
          const inferredStatus: AgentRuntime["status"] =
            runtime?.status ?? (isFullyDone ? "done" : "idle");
          const score = runtime?.score;
          const verdict = runtime?.verdict;
          const colors = LAYER_COLORS[String(agent.layer)];
          const isFocused = focusedAgent === agent.id;
          const ringClass = STATUS_RING[inferredStatus];

          return (
            <g
              key={agent.id}
              transform={`translate(${agent.x}, ${agent.y})`}
              className="cursor-pointer"
              onMouseEnter={() => setHoverId(agent.id)}
              onMouseLeave={() => setHoverId((id) => (id === agent.id ? null : id))}
              onClick={() => onFocusAgent?.(isFocused ? null : agent.id)}
              role="button"
              aria-label={`${agent.label}: ${inferredStatus}${score !== undefined ? `, score ${Math.round(score)}` : ""}`}
            >
              {/* Pulsing halo when active */}
              {inferredStatus === "active" && (
                <motion.circle
                  r={3.6}
                  className={cn(colors.fill, "opacity-60")}
                  animate={{ r: [3.6, 5.5, 3.6], opacity: [0.5, 0.15, 0.5] }}
                  transition={{ duration: 1.6, repeat: Infinity }}
                />
              )}
              {/* Focus ring */}
              {isFocused && (
                <circle
                  r={4.2}
                  className="fill-none stroke-emerald-500 dark:stroke-emerald-400"
                  strokeWidth={0.35}
                  strokeDasharray="0.6 0.4"
                />
              )}
              {/* Node circle */}
              <motion.circle
                r={3}
                className={cn(
                  ringClass,
                  inferredStatus === "idle" ? "fill-white dark:fill-slate-900" : colors.fill,
                  inferredStatus === "fallback" && "fill-amber-100 dark:fill-amber-900/60",
                  inferredStatus === "skipped" && "fill-sky-100 dark:fill-sky-900/60",
                )}
                strokeWidth={0.45}
                animate={{
                  scale: inferredStatus === "active" ? [1, 1.15, 1] : 1,
                }}
                transition={{ duration: 1.2, repeat: inferredStatus === "active" ? Infinity : 0 }}
              />
              {/* Score (centred) */}
              {(inferredStatus === "done" || inferredStatus === "fallback") &&
                score !== undefined && (
                  <text
                    x={0}
                    y={0.6}
                    textAnchor="middle"
                    className={cn("font-bold", colors.text)}
                    style={{ fontSize: "2.1px" }}
                  >
                    {Math.round(score)}
                  </text>
                )}
              {/* Status icons (skipped / fallback) */}
              {inferredStatus === "skipped" && (
                <text
                  x={0}
                  y={0.6}
                  textAnchor="middle"
                  className="fill-sky-600 dark:fill-sky-400"
                  style={{ fontSize: "2.1px" }}
                  >
                  ↷
                </text>
              )}
              {inferredStatus === "fallback" && score === undefined && (
                <text
                  x={0}
                  y={0.6}
                  textAnchor="middle"
                  className="fill-amber-600 dark:fill-amber-400"
                  style={{ fontSize: "2.1px" }}
                  >
                  !
                </text>
              )}
              {/* Label (below) */}
              <text
                x={0}
                y={5.2}
                textAnchor="middle"
                className="fill-slate-600 dark:fill-slate-300 font-medium"
                style={{ fontSize: "2.1px" }}
              >
                {agent.label}
              </text>
              {verdict && (
                <text
                  x={0}
                  y={7.6}
                  textAnchor="middle"
                  className="fill-violet-600 dark:fill-violet-400 font-semibold"
                  style={{ fontSize: "1.8px" }}
                >
                  {verdict.replace("_", " ")}
                </text>
              )}
            </g>
          );
        })}
        </svg>

        {/* Hover tooltip (HTML overlay so we get full text wrapping & long content) */}
        {hovered && hoveredNode && (
          <HoverTooltip
            x={hoveredNode.x}
            y={hoveredNode.y}
            runtime={hovered}
            label={hoveredNode.label}
            startedAt={startedAt}
          />
        )}
      </div>

      {/* Status footer */}
      <div className="mt-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-slate-200/70 pt-3 text-xs text-muted-foreground shrink-0 dark:border-slate-800">
        <div className="flex items-center gap-3 flex-wrap">
          <LegendDot color="bg-slate-400" label="Pre-flight" />
          <LegendDot color="bg-emerald-500" label="Specialists" />
          <LegendDot color="bg-cyan-500" label="Bias audit" />
          <LegendDot color="bg-amber-500" label="Debate" />
          <LegendDot color="bg-violet-500" label="Insights" />
        </div>
        <div className="font-mono text-[11px] flex items-center gap-3 tabular-nums">
          <span>
            {Object.values(agents).filter((s) => s.status === "active").length} active
          </span>
          <span>
            {
              Object.values(agents).filter(
                (s) => s.status === "done" || s.status === "fallback",
              ).length
            }{" "}
            complete
          </span>
          {Object.values(agents).filter((s) => s.status === "fallback").length > 0 && (
            <span className="text-amber-600 dark:text-amber-400">
              {Object.values(agents).filter((s) => s.status === "fallback").length} fallback
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function DebateEdge({
  from,
  to,
  active,
}: {
  from: [number, number];
  to: [number, number];
  active: boolean;
}) {
  return (
    <g>
      <line
        x1={from[0]}
        y1={from[1]}
        x2={to[0]}
        y2={to[1]}
        strokeWidth={0.25}
        className={cn(
          "stroke-amber-500 transition-opacity",
          active ? "opacity-100" : "opacity-30",
        )}
      />
      {active && (
        <motion.circle
          r={0.5}
          className="fill-amber-500"
          initial={{ cx: from[0], cy: from[1], opacity: 0 }}
          animate={{ cx: to[0], cy: to[1], opacity: [0, 1, 0] }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
    </g>
  );
}

function HoverTooltip({
  x,
  y,
  runtime,
  label,
  startedAt,
}: {
  x: number;
  y: number;
  runtime: AgentRuntime;
  label: string;
  startedAt?: number | null;
}) {
  const status = runtime.status;
  const statusLabel: Record<AgentRuntime["status"], string> = {
    idle: "Idle",
    active: "Running",
    done: "Done",
    fallback: "Fallback",
    skipped: "Skipped",
    error: "Error",
  };

  const statusColor: Record<AgentRuntime["status"], string> = {
    idle: "text-slate-500",
    active: "text-emerald-600",
    done: "text-emerald-600",
    fallback: "text-amber-600",
    skipped: "text-sky-600",
    error: "text-red-600",
  };

  // Convert SVG (0..100) coords to CSS percentages.  Use translate to keep the
  // tooltip from running off the right edge.
  // Map SVG coords (0..100 agent space) into the padded viewBox canvas.
  const goLeft = x > 60;
  const goUp = y > 60;
  const cssLeft = `calc(${(x + 6) * (100 / 112)}% + ${goLeft ? "-12px" : "12px"})`;
  const cssTop = `calc(${(y + 8) * (100 / 118)}% + ${goUp ? "-12px" : "12px"})`;
  const transform = `translate(${goLeft ? "-100%" : "0"}, ${goUp ? "-100%" : "0"})`;

  const sinceStart =
    runtime.firstSeenAt && startedAt
      ? `${((runtime.firstSeenAt - startedAt) / 1000).toFixed(1)}s after start`
      : null;

  return (
    <div
      className="absolute z-20 pointer-events-none w-[220px] rounded-lg border bg-popover/95 backdrop-blur-sm shadow-lg p-2.5"
      style={{ left: cssLeft, top: cssTop, transform }}
    >
      <div className="flex items-center justify-between gap-2 mb-1">
        <span className="text-sm font-semibold truncate">{label}</span>
        <span
          className={cn(
            "text-[10px] uppercase tracking-wider font-bold",
            statusColor[status],
          )}
        >
          {statusLabel[status]}
        </span>
      </div>
      <div className="text-[11px] text-muted-foreground flex flex-wrap gap-x-3 gap-y-0.5 mb-1">
        {runtime.score !== undefined && (
          <span>
            Score:{" "}
            <span className="font-mono font-bold text-foreground">
              {Math.round(runtime.score)}
            </span>
          </span>
        )}
        {runtime.latencyMs !== undefined && runtime.latencyMs > 0 && (
          <span>
            Latency:{" "}
            <span className="font-mono font-bold text-foreground">
              {(runtime.latencyMs / 1000).toFixed(1)}s
            </span>
          </span>
        )}
        <span>
          Events: <span className="font-mono">{runtime.thoughtCount}</span>
        </span>
      </div>
      {sinceStart && (
        <div className="text-[10px] text-muted-foreground italic mb-1">
          Started {sinceStart}
        </div>
      )}
      {runtime.lastThought && (
        <div className="border-t pt-1.5 mt-1.5">
          <p className="text-xs leading-snug line-clamp-3 text-foreground/90">
            {runtime.lastThought.thought}
          </p>
        </div>
      )}
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={cn("inline-block h-2 w-2 rounded-full", color)} />
      <span>{label}</span>
    </div>
  );
}
