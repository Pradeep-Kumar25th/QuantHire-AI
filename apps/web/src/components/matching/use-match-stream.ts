"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { api } from "@/lib/api";

export type AgentPhase =
  | "OBSERVE"
  | "THINK"
  | "PLAN"
  | "ACT"
  | "REFLECT"
  | "SWARM"
  | "DEBATE"
  | "INSIGHT"
  | "DONE";

export type AgentState =
  | "PRE_FLIGHT"
  | "SWARM"
  | "DEBATE"
  | "INSIGHT"
  | "DONE"
  | string; // forward-compat for new states

export type AgentThought = {
  agent: string;
  phase: AgentPhase;
  thought: string;
  action?: string | null;
  state?: AgentState | null;
  timestamp?: string | null;
  autonomous?: boolean;
  metadata?: Record<string, any> | null;
};

export type MatchResult = Record<string, any>;

export type StreamStatus =
  | "idle"
  | "connecting"
  | "running"
  | "reconnecting"
  | "done"
  | "error";

interface StartArgs {
  candidate_id: string;
  jd_id: string;
  weights?: Record<string, number>;
}

/** Per-agent runtime state derived from the thought stream. */
export type AgentRuntime = {
  status: "idle" | "active" | "done" | "fallback" | "skipped" | "error";
  firstSeenAt?: number;
  lastSeenAt?: number;
  latencyMs?: number;
  score?: number;
  verdict?: string;
  lastThought?: AgentThought;
  thoughtCount: number;
};

/** High-level signals surfaced in the HUD. */
export type RunSignals = {
  cacheHit: boolean;
  fastPath: "reject" | "strong_hire" | null;
  criticSkipped: boolean;
  criticDisabled: boolean;
  debateRoundsExecuted?: number;
  fallbacks: string[]; // agent names that hit fallback
  swarmHealth?: {
    specialist_count?: number;
    specialists_neutral_fallback?: number;
    all_specialists_real_scores?: boolean;
    risk_agent_placeholder?: boolean;
    bias_auditor_placeholder?: boolean;
  };
  jdHygiene?: {
    severity: "ok" | "warn" | "block";
    summary: string;
    issueCount: number;
  };
  groundedness?: {
    overallPct: number; // 0..1
    fabricated: number;
    total: number;
    rawTextAvailable: boolean;
  };
  locationFit?: {
    fit: "ok" | "warn" | "block" | "unknown";
    summary: string;
    requiresRelocation: boolean;
    isRemoteRole: boolean | null;
    timeZoneOverlapHours: number | null;
  };
};

interface UseMatchStreamReturn {
  status: StreamStatus;
  thoughts: AgentThought[];
  result: MatchResult | null;
  error: string | null;
  /** Wall-clock millis since `start` was called (live, updates every 200ms). */
  elapsedMs: number;
  /** Millis since the last event arrived — useful to detect stalls. */
  sinceLastEventMs: number;
  /** Highest-numbered layer we've seen activity in. */
  currentLayer: 1 | 2 | 3 | 4 | null;
  currentState: AgentState | null;
  agents: Record<string, AgentRuntime>;
  signals: RunSignals;
  start: (args: StartArgs) => void;
  stop: () => void;
  reset: () => void;
}

const STATE_TO_LAYER: Record<string, 1 | 2 | 3 | 4> = {
  PRE_FLIGHT: 1,
  SWARM: 2,
  DEBATE: 3,
  INSIGHT: 4,
  DONE: 4,
};

const FALLBACK_NEEDLES = [
  "neutral fallback",
  "defaulting to low-risk",
  "defaulting to fair assumption",
  "fast-path",
  "specialist failed",
];

function isFallback(thought: AgentThought): boolean {
  const haystack = (thought.thought || "").toLowerCase();
  return FALLBACK_NEEDLES.some((n) => haystack.includes(n));
}

function tsToEpoch(ts?: string | null): number | undefined {
  if (!ts) return undefined;
  const t = Date.parse(ts);
  return Number.isFinite(t) ? t : undefined;
}

/**
 * React hook that opens an EventSource against the FastAPI SSE endpoint
 * and streams agent thoughts + the final match result.
 *
 * Adds production-grade behaviour the previous version lacked:
 *  - One-shot reconnection on transient SSE drops (during `running`).
 *  - Live elapsed-millisecond ticker for the HUD.
 *  - Per-agent runtime derivation (status, latency, score) so callers
 *    (visualiser, tooltip, focus) don't recompute it on every render.
 *  - Surface high-level run signals (cache hit, fast-path, critic skipped,
 *    fallbacks, swarm health) — these are the "is something wrong?" cues
 *    a recruiter / ops user must see at a glance.
 */
export function useMatchStream(): UseMatchStreamReturn {
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [thoughts, setThoughts] = useState<AgentThought[]>([]);
  const [result, setResult] = useState<MatchResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [lastEventAt, setLastEventAt] = useState<number | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());

  const sourceRef = useRef<EventSource | null>(null);
  const lastArgsRef = useRef<StartArgs | null>(null);
  const reconnectAttemptedRef = useRef<boolean>(false);
  const finishedRef = useRef<boolean>(false);

  // ---- live ticker ---------------------------------------------------------
  useEffect(() => {
    if (status !== "running" && status !== "connecting" && status !== "reconnecting") {
      return;
    }
    const id = window.setInterval(() => setNow(Date.now()), 200);
    return () => window.clearInterval(id);
  }, [status]);

  const cleanup = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    cleanup();
    finishedRef.current = false;
    reconnectAttemptedRef.current = false;
    lastArgsRef.current = null;
    setStatus("idle");
    setThoughts([]);
    setResult(null);
    setError(null);
    setStartedAt(null);
    setLastEventAt(null);
  }, [cleanup]);

  const stop = useCallback(() => {
    cleanup();
    finishedRef.current = true;
    setStatus((prev) => (prev === "error" ? prev : "done"));
  }, [cleanup]);

  // ---- core SSE wiring -----------------------------------------------------
  const openConnection = useCallback(
    (args: StartArgs, isReconnect = false) => {
      cleanup();
      const url = api.jobMatching.streamUrl(
        args.candidate_id,
        args.jd_id,
        args.weights,
      );
      const source = new EventSource(url, { withCredentials: true });
      sourceRef.current = source;
      setStatus(isReconnect ? "reconnecting" : "connecting");

      source.addEventListener("open", () => {
        setStatus("running");
        setLastEventAt(Date.now());
      });

      source.addEventListener("thought", (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data) as AgentThought;
          setThoughts((prev) => [...prev, payload]);
          setLastEventAt(Date.now());
        } catch (err) {
          console.warn("Failed to parse thought event:", err);
        }
      });

      source.addEventListener("result", (event: MessageEvent) => {
        try {
          const payload = JSON.parse(event.data) as MatchResult;
          setResult(payload);
          setLastEventAt(Date.now());
        } catch (err) {
          console.warn("Failed to parse result event:", err);
        }
      });

      source.addEventListener("error", (event: MessageEvent) => {
        try {
          const payload = event.data ? JSON.parse(event.data) : null;
          setError(payload?.message || "Stream encountered an error");
        } catch {
          setError("Stream encountered an error");
        }
        finishedRef.current = true;
        setStatus("error");
        cleanup();
      });

      source.addEventListener("close", () => {
        finishedRef.current = true;
        setStatus((prev) => (prev === "error" ? prev : "done"));
        cleanup();
      });

      // Browser-level error (network drop / TLS reset).  EventSource normally
      // auto-reconnects, but the FastAPI route restarts the swarm from scratch
      // so a naive reconnect would produce duplicated thought events.  We
      // attempt ONE silent reconnect AND wipe the in-flight thought list so
      // the UI shows a clean second-run timeline instead of a chimera.
      source.onerror = () => {
        if (!sourceRef.current) return;
        if (sourceRef.current.readyState !== EventSource.CLOSED) return;
        if (finishedRef.current) {
          cleanup();
          setStatus((prev) => (prev === "done" || prev === "error" ? prev : "done"));
          return;
        }
        if (!reconnectAttemptedRef.current && lastArgsRef.current) {
          reconnectAttemptedRef.current = true;
          // Wipe the partial run so the second attempt's events render cleanly.
          setThoughts([]);
          setResult(null);
          setLastEventAt(Date.now());
          openConnection(lastArgsRef.current, true);
          return;
        }
        cleanup();
        setStatus((prev) => (prev === "done" || prev === "error" ? prev : "error"));
        setError((prev) => prev ?? "Connection lost. Please retry the match.");
      };
    },
    [cleanup],
  );

  const start = useCallback(
    (args: StartArgs) => {
      lastArgsRef.current = args;
      reconnectAttemptedRef.current = false;
      finishedRef.current = false;
      setThoughts([]);
      setResult(null);
      setError(null);
      const t = Date.now();
      setStartedAt(t);
      setLastEventAt(t);
      setNow(t);
      openConnection(args, false);
    },
    [openConnection],
  );

  useEffect(() => () => cleanup(), [cleanup]);

  // ---- derived state -------------------------------------------------------
  const elapsedMs = startedAt
    ? (status === "done" || status === "error"
        ? Math.max(0, (lastEventAt ?? now) - startedAt)
        : Math.max(0, now - startedAt))
    : 0;

  const sinceLastEventMs = lastEventAt && status === "running"
    ? Math.max(0, now - lastEventAt)
    : 0;

  const { agents, currentLayer, currentState, signals } = useMemo(() => {
    const agentsMap: Record<string, AgentRuntime> = {};
    const fallbacks = new Set<string>();
    let cacheHit = false;
    let fastPath: "reject" | "strong_hire" | null = null;
    let criticSkipped = false;
    let criticDisabled = false;
    let debateRoundsExecuted: number | undefined;
    let mostRecentLayer: 1 | 2 | 3 | 4 | null = null;
    let mostRecentState: AgentState | null = null;

    for (const t of thoughts) {
      const epoch = tsToEpoch(t.timestamp);
      const existing = agentsMap[t.agent] ?? {
        status: "active",
        thoughtCount: 0,
      };
      existing.thoughtCount += 1;
      existing.lastThought = t;
      if (epoch !== undefined) {
        if (existing.firstSeenAt === undefined) existing.firstSeenAt = epoch;
        existing.lastSeenAt = epoch;
        if (existing.firstSeenAt !== undefined) {
          existing.latencyMs = existing.lastSeenAt - existing.firstSeenAt;
        }
      }

      // status promotion
      if (t.metadata?.skipped === true) {
        existing.status = "skipped";
      } else if (isFallback(t)) {
        existing.status = "fallback";
        fallbacks.add(t.agent);
      } else if (t.phase === "REFLECT" || t.phase === "DONE" || t.phase === "INSIGHT") {
        if (existing.status !== "fallback" && existing.status !== "skipped") {
          existing.status = "done";
        }
      } else if (existing.status !== "done" && existing.status !== "fallback") {
        existing.status = "active";
      }

      // surface scores
      if (t.metadata?.score !== undefined) existing.score = Number(t.metadata.score);
      if (t.metadata?.final_score !== undefined) {
        existing.score = Number(t.metadata.final_score);
      }
      if (t.metadata?.verdict !== undefined) existing.verdict = String(t.metadata.verdict);

      agentsMap[t.agent] = existing;

      // page-level signals
      if (t.metadata?.cache === "hit") cacheHit = true;
      if (t.metadata?.fast_path === "reject") fastPath = "reject";
      if (t.metadata?.fast_path === "strong_hire") fastPath = "strong_hire";
      if (t.agent === "Critic" && t.metadata?.skipped === true) criticSkipped = true;

      // current state / layer
      if (t.state && STATE_TO_LAYER[t.state]) {
        mostRecentState = t.state;
        mostRecentLayer = STATE_TO_LAYER[t.state];
      }
    }

    // Pull richer signals from the final result if we have it.
    const meta = (result?.metadata ?? {}) as Record<string, any>;
    if (meta.critic_skipped) criticSkipped = true;
    if (meta.critic_disabled) criticDisabled = true;
    if (typeof meta.debate_rounds_executed === "number") {
      debateRoundsExecuted = meta.debate_rounds_executed;
    }
    if (meta.served_from_cache) cacheHit = true;

    // Location fit (pre-flight)
    let locationFit: RunSignals["locationFit"] | undefined;
    const lf = meta.location_fit as Record<string, any> | undefined;
    if (lf && typeof lf === "object") {
      const fitVal = (lf.fit as string) || "unknown";
      if (fitVal === "ok" || fitVal === "warn" || fitVal === "block" || fitVal === "unknown") {
        locationFit = {
          fit: fitVal,
          summary: String(lf.summary || ""),
          requiresRelocation: lf.requires_relocation === true,
          isRemoteRole:
            typeof lf.is_remote_role === "boolean" ? lf.is_remote_role : null,
          timeZoneOverlapHours:
            typeof lf.time_zone_overlap_hours === "number"
              ? lf.time_zone_overlap_hours
              : null,
        };
      }
    }

    // Groundedness (deterministic verifier output)
    let groundedness: RunSignals["groundedness"] | undefined;
    const grnd = meta.groundedness as Record<string, any> | undefined;
    if (grnd && typeof grnd === "object") {
      groundedness = {
        overallPct: typeof grnd.overall_pct === "number" ? grnd.overall_pct : 1,
        fabricated:
          typeof grnd.fabricated_evidence === "number" ? grnd.fabricated_evidence : 0,
        total: typeof grnd.total_evidence === "number" ? grnd.total_evidence : 0,
        rawTextAvailable: grnd.raw_text_available !== false,
      };
    }

    // JD hygiene severity
    let jdHygiene: RunSignals["jdHygiene"] | undefined;
    const hyg = meta.jd_hygiene as Record<string, any> | undefined;
    if (hyg && typeof hyg === "object") {
      const issues =
        (Array.isArray(hyg.contradictions) ? hyg.contradictions.length : 0) +
        (Array.isArray(hyg.protected_attribute_language)
          ? hyg.protected_attribute_language.length
          : 0) +
        (Array.isArray(hyg.unrealistic_requirements)
          ? hyg.unrealistic_requirements.length
          : 0) +
        (Array.isArray(hyg.missing_critical_fields)
          ? hyg.missing_critical_fields.length
          : 0);
      const sev = (hyg.severity as string) || "ok";
      if (sev === "ok" || sev === "warn" || sev === "block") {
        jdHygiene = {
          severity: sev,
          summary: String(hyg.summary || ""),
          issueCount: issues,
        };
      }
    }

    return {
      agents: agentsMap,
      currentLayer: mostRecentLayer,
      currentState: mostRecentState,
      signals: {
        cacheHit,
        fastPath,
        criticSkipped,
        criticDisabled,
        debateRoundsExecuted,
        fallbacks: Array.from(fallbacks),
        swarmHealth: meta.swarm_health,
        jdHygiene,
        groundedness,
        locationFit,
      },
    };
  }, [thoughts, result]);

  return {
    status,
    thoughts,
    result,
    error,
    elapsedMs,
    sinceLastEventMs,
    currentLayer,
    currentState,
    agents,
    signals,
    start,
    stop,
    reset,
  };
}
