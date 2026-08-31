"use client";

import { cn } from "@/lib/utils";

const VERDICT_STYLES: Record<
  string,
  { label: string; bg: string; text: string; border: string }
> = {
  STRONG_HIRE: {
    label: "Strong Hire",
    bg: "bg-emerald-500",
    text: "text-white",
    border: "border-emerald-600",
  },
  HIRE: {
    label: "Hire",
    bg: "bg-emerald-100 dark:bg-emerald-950",
    text: "text-emerald-900 dark:text-emerald-300",
    border: "border-emerald-300 dark:border-emerald-700",
  },
  CONSIDER: {
    label: "Consider",
    bg: "bg-amber-100 dark:bg-amber-950",
    text: "text-amber-900 dark:text-amber-300",
    border: "border-amber-300 dark:border-amber-700",
  },
  NO_HIRE: {
    label: "No Hire",
    bg: "bg-red-100 dark:bg-red-950",
    text: "text-red-900 dark:text-red-300",
    border: "border-red-300 dark:border-red-700",
  },
  STRONG_NO_HIRE: {
    label: "Strong No Hire",
    bg: "bg-red-500",
    text: "text-white",
    border: "border-red-600",
  },
};

interface VerdictBadgeProps {
  verdict: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function VerdictBadge({ verdict, size = "md", className }: VerdictBadgeProps) {
  const style = VERDICT_STYLES[verdict] ?? VERDICT_STYLES.CONSIDER;
  const sizeClasses =
    size === "lg"
      ? "px-4 py-1.5 text-sm"
      : size === "sm"
        ? "px-2 py-0.5 text-[10px]"
        : "px-3 py-1 text-xs";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-bold uppercase tracking-wider",
        style.bg,
        style.text,
        style.border,
        sizeClasses,
        className,
      )}
    >
      {style.label}
    </span>
  );
}
