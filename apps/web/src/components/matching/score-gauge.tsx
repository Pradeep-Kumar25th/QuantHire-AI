"use client";

import { motion } from "framer-motion";

import { cn } from "@/lib/utils";
import { VerdictBadge } from "./verdict-badge";

interface ScoreGaugeProps {
  score: number;
  verdict?: string;
  confidence?: number;
  className?: string;
  size?: number;
}

export function ScoreGauge({
  score,
  verdict,
  confidence,
  className,
  size = 220,
}: ScoreGaugeProps) {
  const clamped = Math.max(0, Math.min(100, score));
  const radius = (size - 24) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (clamped / 100) * circumference;

  const colorClass =
    clamped >= 80
      ? "stroke-emerald-500"
      : clamped >= 65
        ? "stroke-emerald-400"
        : clamped >= 50
          ? "stroke-amber-500"
          : "stroke-red-500";

  return (
    <div
      className={cn(
        "relative flex flex-col items-center justify-center",
        className,
      )}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        className="absolute inset-0 -rotate-90"
        viewBox={`0 0 ${size} ${size}`}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          className="stroke-muted"
          strokeWidth={12}
          fill="none"
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          className={cn(colorClass, "transition-colors")}
          strokeWidth={12}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: "easeOut" }}
        />
      </svg>
      <div className="relative z-10 flex flex-col items-center">
        <motion.span
          className="text-5xl font-bold tabular-nums tracking-tight"
          initial={{ opacity: 0, scale: 0.85 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.6 }}
        >
          {clamped.toFixed(0)}
        </motion.span>
        <span className="text-xs uppercase tracking-wider text-muted-foreground -mt-1">
          / 100
        </span>
        {verdict && (
          <div className="mt-3">
            <VerdictBadge verdict={verdict} size="md" />
          </div>
        )}
        {confidence !== undefined && (
          <div className="mt-1.5 text-[10px] uppercase tracking-wider text-muted-foreground font-mono">
            confidence {Math.round(confidence * 100)}%
          </div>
        )}
      </div>
    </div>
  );
}
