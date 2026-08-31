"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

const data = [
  { name: "Mon", applications: 12, interviews: 4 },
  { name: "Tue", applications: 19, interviews: 7 },
  { name: "Wed", applications: 15, interviews: 5 },
  { name: "Thu", applications: 22, interviews: 9 },
  { name: "Fri", applications: 18, interviews: 6 },
  { name: "Sat", applications: 8, interviews: 2 },
  { name: "Sun", applications: 5, interviews: 1 },
];

export function ActivityChart() {
  return (
    <ResponsiveContainer width="100%" height={350}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis
          dataKey="name"
          stroke="hsl(var(--brand-gray))"
          fontSize={12}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="hsl(var(--brand-gray))"
          fontSize={12}
          tickLine={false}
          axisLine={false}
          tickFormatter={(value) => `${value}`}
        />
        <Tooltip />
        <Line
          type="monotone"
          dataKey="applications"
          stroke="hsl(var(--primary))"
          strokeWidth={2}
        />
        <Line
          type="monotone"
          dataKey="interviews"
          stroke="hsl(var(--muted-foreground))"
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

