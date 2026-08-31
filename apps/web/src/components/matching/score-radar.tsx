"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

import { cn } from "@/lib/utils";

const DIMENSION_LABELS: Record<string, string> = {
  skills: "Skills",
  experience: "Experience",
  education: "Education",
  domain: "Domain",
  culture: "Culture",
  growth: "Growth",
  projects: "Projects",
  risk: "Risk (inv.)",
};

interface DimensionInput {
  dimension: string;
  score: number;
}

interface ScoreRadarProps {
  scores: DimensionInput[];
  className?: string;
}

export function ScoreRadar({ scores, className }: ScoreRadarProps) {
  const data = scores.map((s) => ({
    dimension: DIMENSION_LABELS[s.dimension] ?? s.dimension,
    score: Math.max(0, Math.min(100, Number(s.score ?? 0))),
    fullMark: 100,
  }));

  return (
    <div className={cn("h-[320px] w-full", className)}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} cx="50%" cy="52%" outerRadius="82%">
          <PolarGrid stroke="currentColor" className="opacity-15" />
          <PolarAngleAxis
            dataKey="dimension"
            tick={{ fontSize: 11, fill: "currentColor" }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 100]}
            tick={{ fontSize: 9, fill: "currentColor", opacity: 0.5 }}
            stroke="currentColor"
            className="opacity-20"
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke="hsl(160 70% 45%)"
            fill="hsl(160 70% 45%)"
            fillOpacity={0.35}
            strokeWidth={2}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--background))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "8px",
              fontSize: 12,
            }}
            formatter={(value: number) => [`${value.toFixed(0)} / 100`, "Score"]}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
