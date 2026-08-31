"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  AlertTriangle,
  ArrowDownToLine,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ClipboardCopy,
  Download,
  Eye,
  MessageSquare,
  Pause,
  Play,
  RefreshCw,
  Search,
  Sparkles,
  Target,
  Workflow,
  X,
  Zap,
  type LucideIcon,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { AgentPhase, AgentThought } from "./use-match-stream";

const PHASE_META: Record<
  AgentPhase,
  { icon: LucideIcon; color: string; label: string; bg: string }
> = {
  OBSERVE: { icon: Eye, color: "text-sky-600 dark:text-sky-400", label: "Observe", bg: "bg-sky-50 dark:bg-sky-950/40" },
  THINK: { icon: Brain, color: "text-indigo-600 dark:text-indigo-400", label: "Think", bg: "bg-indigo-50 dark:bg-indigo-950/40" },
  PLAN: { icon: Target, color: "text-amber-600 dark:text-amber-400", label: "Plan", bg: "bg-amber-50 dark:bg-amber-950/40" },
  ACT: { icon: Zap, color: "text-emerald-600 dark:text-emerald-400", label: "Act", bg: "bg-emerald-50 dark:bg-emerald-950/40" },
  REFLECT: { icon: RefreshCw, color: "text-violet-600 dark:text-violet-400", label: "Reflect", bg: "bg-violet-50 dark:bg-violet-950/40" },
  SWARM: { icon: Workflow, color: "text-emerald-700 dark:text-emerald-400", label: "Swarm", bg: "bg-emerald-50 dark:bg-emerald-950/40" },
  DEBATE: { icon: MessageSquare, color: "text-amber-700 dark:text-amber-400", label: "Debate", bg: "bg-amber-50 dark:bg-amber-950/40" },
  INSIGHT: { icon: Sparkles, color: "text-violet-700 dark:text-violet-400", label: "Insight", bg: "bg-violet-50 dark:bg-violet-950/40" },
  DONE: { icon: CheckCircle2, color: "text-green-700 dark:text-green-400", label: "Done", bg: "bg-green-50 dark:bg-green-950/40" },
};

const FALLBACK_NEEDLES = [
  "neutral fallback",
  "defaulting to low-risk",
  "defaulting to fair assumption",
  "fast-path",
  "specialist failed",
  "could not produce",
];

const QUICK_FILTERS: { id: string; label: string }[] = [
  { id: "all", label: "All" },
  { id: "swarm", label: "Swarm" },
  { id: "debate", label: "Debate" },
  { id: "insight", label: "Insights" },
  { id: "fallback", label: "Fallbacks" },
];

const PANEL_SHELL =
  "rounded-xl border border-slate-200/80 bg-card shadow-sm dark:border-slate-800";

interface AgentThoughtsStreamProps {
  thoughts: AgentThought[];
  className?: string;
  emptyState?: string;
  /** Fixed Tailwind height class when fillHeight is false. */
  height?: string;
  /** Stretch to parent flex height instead of using a fixed pixel height. */
  fillHeight?: boolean;
  focusedAgent?: string | null;
  onClearFocus?: () => void;
  startedAt?: number | null;
}

function isFallback(t: AgentThought): boolean {
  const haystack = (t.thought || "").toLowerCase();
  return FALLBACK_NEEDLES.some((n) => haystack.includes(n));
}

function relativeTimeLabel(ts?: string | null, startedAt?: number | null): string | null {
  if (!ts) return null;
  const epoch = Date.parse(ts);
  if (!Number.isFinite(epoch)) return null;
  if (startedAt) {
    const delta = Math.max(0, epoch - startedAt);
    const s = (delta / 1000).toFixed(1);
    return `+${s}s`;
  }
  const d = new Date(epoch);
  return d.toLocaleTimeString();
}

export function AgentThoughtsStream({
  thoughts,
  className,
  emptyState = "Waiting for the swarm to come online…",
  height = "h-[460px]",
  fillHeight = false,
  focusedAgent,
  onClearFocus,
  startedAt,
}: AgentThoughtsStreamProps) {
  // Anchor sits inside the ScrollArea Viewport. We resolve the actual
  // scrolling element by walking upward to `[data-radix-scroll-area-viewport]`
  // — that's the element whose `scrollTop` / `scrollHeight` are correct.
  const innerAnchorRef = useRef<HTMLDivElement>(null);
  const scrollElRef = useRef<HTMLDivElement | null>(null);

  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState<string>("");
  const [density, setDensity] = useState<"compact" | "comfortable">("comfortable");
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  // ---- smart auto-scroll ---------------------------------------------------
  // Auto-stick to bottom UNLESS the user scrolls up. Re-engage when they
  // scroll back to (within 24px of) the bottom or click the resume button.
  const handleScroll = useCallback(() => {
    const v = scrollElRef.current;
    if (!v) return;
    const distFromBottom = v.scrollHeight - v.scrollTop - v.clientHeight;
    if (distFromBottom > 60 && autoScroll) {
      setAutoScroll(false);
    } else if (distFromBottom < 24 && !autoScroll) {
      setAutoScroll(true);
    }
  }, [autoScroll]);

  // ---- filtering & search --------------------------------------------------
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return thoughts
      .map((t, idx) => ({ t, idx }))
      .filter(({ t }) => {
        if (focusedAgent && t.agent !== focusedAgent) return false;
        if (filter === "swarm" && t.state !== "SWARM") return false;
        if (filter === "debate" && t.state !== "DEBATE") return false;
        if (filter === "insight" && t.state !== "INSIGHT") return false;
        if (filter === "fallback" && !isFallback(t)) return false;
        if (q) {
          const haystack = `${t.agent} ${t.thought} ${t.action ?? ""}`.toLowerCase();
          if (!haystack.includes(q)) return false;
        }
        return true;
      });
  }, [thoughts, filter, search, focusedAgent]);

  const fallbackCount = useMemo(
    () => thoughts.reduce((acc, t) => acc + (isFallback(t) ? 1 : 0), 0),
    [thoughts],
  );

  // Bind the scroll listener to the Radix viewport (ancestor of our anchor).
  useEffect(() => {
    const el = innerAnchorRef.current?.closest(
      "[data-radix-scroll-area-viewport]",
    ) as HTMLDivElement | null;
    if (!el) return;
    scrollElRef.current = el;
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [handleScroll, filtered.length, fillHeight]);

  useEffect(() => {
    if (!autoScroll) return;
    const v = scrollElRef.current;
    if (!v) return;
    v.scrollTop = v.scrollHeight;
  }, [thoughts.length, autoScroll, filtered.length]);

  // ---- copy / download -----------------------------------------------------
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(thoughts, null, 2));
    } catch {
      /* clipboard blocked — ignore silently */
    }
  }, [thoughts]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([JSON.stringify(thoughts, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `agent-thoughts-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [thoughts]);

  return (
    <div
      className={cn(
        PANEL_SHELL,
        "flex flex-col min-h-0 w-full overflow-hidden",
        fillHeight && "h-full",
        className,
      )}
    >
      {/* Header: title + metrics + actions */}
      <div className="flex flex-col gap-2 border-b border-slate-200/70 px-4 py-3 shrink-0 sm:flex-row sm:items-center sm:justify-between dark:border-slate-800">
        <div className="min-w-0">
          <div className="flex items-center gap-2 min-w-0">
            <span className="relative flex h-2.5 w-2.5 shrink-0">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
              <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
            </span>
            <h3 className="text-sm font-semibold tracking-tight truncate">
              Agent reasoning stream
            </h3>
            {focusedAgent && (
              <span className="flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300">
                {focusedAgent}
                {onClearFocus && (
                  <button
                    onClick={onClearFocus}
                    className="hover:bg-emerald-100 dark:hover:bg-emerald-900 rounded-full p-0.5"
                    aria-label="Clear focused agent"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                )}
              </span>
            )}
          </div>
          <p className="mt-0.5 pl-4 text-xs text-muted-foreground">
            Live specialist output · {filtered.length} of {thoughts.length} events
          </p>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <IconButton
            label={autoScroll ? "Pause auto-scroll" : "Resume auto-scroll"}
            onClick={() => setAutoScroll((v) => !v)}
          >
            {autoScroll ? (
              <Pause className="h-3.5 w-3.5" />
            ) : (
              <Play className="h-3.5 w-3.5" />
            )}
          </IconButton>
          <IconButton
            label={density === "compact" ? "Switch to comfortable density" : "Switch to compact density"}
            onClick={() =>
              setDensity((d) => (d === "compact" ? "comfortable" : "compact"))
            }
          >
            {density === "compact" ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronUp className="h-3.5 w-3.5" />
            )}
          </IconButton>
          <IconButton
            label="Copy thoughts as JSON"
            onClick={handleCopy}
            disabled={thoughts.length === 0}
          >
            <ClipboardCopy className="h-3.5 w-3.5" />
          </IconButton>
          <IconButton
            label="Download thoughts JSON"
            onClick={handleDownload}
            disabled={thoughts.length === 0}
          >
            <Download className="h-3.5 w-3.5" />
          </IconButton>
        </div>
      </div>

      {/* Filter & search row */}
      <div className="flex flex-col gap-2.5 border-b border-slate-200/70 bg-muted/15 px-4 py-2.5 shrink-0 dark:border-slate-800">
        <div className="flex items-center gap-1.5 flex-wrap">
          {QUICK_FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={cn(
                "text-[11px] px-2.5 py-1 rounded-md font-medium transition-all border",
                filter === f.id
                  ? "bg-slate-900 border-slate-900 text-white shadow-sm dark:bg-emerald-700 dark:border-emerald-700"
                  : "bg-card border-slate-200/80 text-muted-foreground hover:bg-muted hover:text-foreground dark:border-slate-700",
              )}
            >
              {f.label}
              {f.id === "fallback" && fallbackCount > 0 && (
                <span
                  className={cn(
                    "ml-1 inline-block rounded-full px-1.5 text-[9px] font-bold",
                    filter === f.id
                      ? "bg-white/20 text-white"
                      : "bg-amber-200 text-amber-900",
                  )}
                >
                  {fallbackCount}
                </span>
              )}
            </button>
          ))}
        </div>
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Filter thoughts…"
            className="h-9 w-full text-sm pl-8"
          />
        </div>
      </div>

      {/* Thoughts list — isolated scroll region so headers never overlap entries */}
      <div className="relative flex-1 min-h-0 overflow-hidden">
        <ScrollArea
          className={cn(
            "h-full w-full [&>[data-radix-scroll-area-viewport]]:h-full",
            !fillHeight && height,
          )}
        >
          <div
            ref={innerAnchorRef}
            aria-live="polite"
            aria-relevant="additions"
            aria-busy={thoughts.length === 0}
            className="flex flex-col gap-2.5 px-4 py-3 pb-6"
          >
          {filtered.length === 0 ? (
            <div className="flex min-h-[200px] items-center justify-center py-10 text-center text-sm text-muted-foreground px-4">
              {thoughts.length === 0 ? emptyState : "No thoughts match the current filter."}
            </div>
          ) : (
            <AnimatePresence initial={false}>
              {filtered.map(({ t, idx }) => {
                const meta = PHASE_META[t.phase] ?? PHASE_META.THINK;
                const Icon = meta.icon;
                const fallback = isFallback(t);
                const skipped = t.metadata?.skipped === true;
                const ts = relativeTimeLabel(t.timestamp, startedAt);
                const isExpanded = !!expanded[idx];
                const hasMetadata =
                  t.metadata && Object.keys(t.metadata).length > 0;

                return (
                  <motion.article
                    key={`${t.agent}-${idx}-${t.timestamp ?? idx}`}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.18 }}
                    className={cn(
                      "rounded-xl border shadow-sm transition-colors",
                      density === "compact" ? "px-3 py-2" : "px-3.5 py-2.5",
                      fallback
                        ? "bg-amber-50/70 dark:bg-amber-950/20 border-amber-200/80 dark:border-amber-800"
                        : skipped
                          ? "bg-sky-50/70 dark:bg-sky-950/20 border-sky-200/80 dark:border-sky-800"
                          : "bg-card hover:bg-muted/20 border-slate-200/80 dark:border-slate-800",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <div
                        className={cn(
                          "mt-0.5 rounded-md p-1 shrink-0",
                          fallback
                            ? "text-amber-600 bg-amber-100 dark:bg-amber-900/40"
                            : `${meta.color} ${meta.bg}`,
                        )}
                      >
                        {fallback ? (
                          <AlertTriangle className="h-3.5 w-3.5" />
                        ) : (
                          <Icon className="h-3.5 w-3.5" />
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                          <span className="text-sm font-semibold truncate max-w-[220px]">
                            {t.agent}
                          </span>
                          <span
                            className={cn(
                              "text-[11px] uppercase tracking-wider font-bold",
                              fallback ? "text-amber-700 dark:text-amber-400" : meta.color,
                            )}
                          >
                            {fallback ? "Fallback" : skipped ? "Skipped" : meta.label}
                          </span>
                          {t.state && (
                            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                              · {t.state.toLowerCase()}
                            </span>
                          )}
                          {ts && (
                            <span className="text-[10px] font-mono text-muted-foreground ml-auto tabular-nums">
                              {ts}
                            </span>
                          )}
                        </div>
                        <p
                          className={cn(
                            "text-foreground/90 leading-relaxed mt-0.5",
                            density === "compact" ? "text-sm" : "text-sm leading-relaxed",
                          )}
                        >
                          {t.thought}
                        </p>
                        {t.action && density === "comfortable" && (
                          <p className="text-sm text-muted-foreground italic mt-1">
                            → {t.action}
                          </p>
                        )}
                        {hasMetadata && (
                          <button
                            onClick={() =>
                              setExpanded((e) => ({ ...e, [idx]: !e[idx] }))
                            }
                            className="mt-1 text-[10px] uppercase tracking-wider text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                          >
                            {isExpanded ? (
                              <>
                                <ChevronUp className="h-2.5 w-2.5" />
                                Hide metadata
                              </>
                            ) : (
                              <>
                                <ChevronDown className="h-2.5 w-2.5" />
                                Metadata ({Object.keys(t.metadata!).length})
                              </>
                            )}
                          </button>
                        )}
                        {hasMetadata && isExpanded && (
                          <pre className="mt-1.5 text-[10px] font-mono bg-muted/60 dark:bg-muted/30 rounded p-2 overflow-x-auto leading-tight">
                            {JSON.stringify(t.metadata, null, 2)}
                          </pre>
                        )}
                      </div>
                    </div>
                  </motion.article>
                );
              })}
            </AnimatePresence>
          )}
          </div>
        </ScrollArea>

        {!autoScroll && filtered.length > 0 && (
          <Button
            size="sm"
            variant="default"
            onClick={() => setAutoScroll(true)}
            className="absolute bottom-3 right-4 z-20 shadow-lg gap-1 h-8 text-xs"
          >
            <ArrowDownToLine className="h-3 w-3" />
            Resume tail
          </Button>
        )}
      </div>
    </div>
  );
}

function IconButton({
  children,
  onClick,
  label,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  label: string;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className={cn(
        "h-7 w-7 inline-flex items-center justify-center rounded-md",
        "text-muted-foreground hover:text-foreground hover:bg-muted",
        "transition-colors disabled:opacity-40 disabled:pointer-events-none",
      )}
    >
      {children}
    </button>
  );
}
