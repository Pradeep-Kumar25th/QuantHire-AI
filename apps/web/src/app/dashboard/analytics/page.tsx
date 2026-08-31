"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, TrendingDown, DollarSign, Clock } from "lucide-react";

const applicationsByStage = [
  { name: "Applied", value: 45, color: "#437A8B" },
  { name: "Screening", value: 28, color: "#FFC000" },
  { name: "Assessment", value: 18, color: "#B0B0B0" },
  { name: "Interviewing", value: 12, color: "#363636" },
  { name: "Offer", value: 5, color: "#CC112F" },
];

const timeToHireData = [
  { month: "Jan", days: 35 },
  { month: "Feb", days: 32 },
  { month: "Mar", days: 28 },
  { month: "Apr", days: 25 },
  { month: "May", days: 22 },
  { month: "Jun", days: 20 },
];

const sourceEffectiveness = [
  { source: "Direct Upload", candidates: 120, hired: 8, cost: 50 },
  { source: "LinkedIn", candidates: 85, hired: 12, cost: 200 },
  { source: "Referral", candidates: 45, hired: 15, cost: 100 },
  { source: "Job Boards", candidates: 65, hired: 5, cost: 150 },
];

const aiMetrics = [
  { metric: "Parsing Accuracy", value: 92 },
  { metric: "Match Precision", value: 87 },
  { metric: "Decision Acceptance", value: 73 },
  { metric: "Offer Acceptance", value: 81 },
];

export default function AnalyticsPage() {
  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Analytics & Insights</h2>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Time to Hire</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">20 days</div>
            <p className="text-xs text-brand-teal flex items-center gap-1">
              <TrendingDown className="h-3 w-3" />
              -43% from last year
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Cost per Hire</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">$2,450</div>
            <p className="text-xs text-brand-teal flex items-center gap-1">
              <TrendingDown className="h-3 w-3" />
              -35% from baseline
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Offer Accept Rate</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">81%</div>
            <p className="text-xs text-brand-teal flex items-center gap-1">
              <TrendingUp className="h-3 w-3" />
              +12% improvement
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">AI Efficiency</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">87%</div>
            <p className="text-xs text-muted-foreground">
              Avg. AI accuracy
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="pipeline" className="space-y-4">
        <TabsList>
          <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
          <TabsTrigger value="ai">AI Metrics</TabsTrigger>
        </TabsList>

        <TabsContent value="pipeline" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Applications by Stage</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={applicationsByStage}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={(entry) => `${entry.name}: ${entry.value}`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {applicationsByStage.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Time to Hire Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={timeToHireData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="month" />
                    <YAxis />
                    <Tooltip />
                    <Line
                      type="monotone"
                      dataKey="days"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="performance" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Hiring Funnel Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[
                  { stage: "Applied", count: 234, conversion: 100 },
                  { stage: "Screening", count: 156, conversion: 67 },
                  { stage: "Assessment", count: 94, conversion: 60 },
                  { stage: "Interview", count: 52, conversion: 55 },
                  { stage: "Offer", count: 18, conversion: 35 },
                  { stage: "Hired", count: 8, conversion: 44 },
                ].map((item) => (
                  <div key={item.stage} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{item.stage}</span>
                      <span className="text-muted-foreground">
                        {item.count} candidates ({item.conversion}% conversion)
                      </span>
                    </div>
                    <Progress value={item.conversion} />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sources" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Source Effectiveness</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={sourceEffectiveness}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="source" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="candidates" fill="hsl(var(--primary))" />
                  <Bar dataKey="hired" fill="hsl(var(--chart-2))" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="ai" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>AI Agent Performance Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {aiMetrics.map((metric) => (
                  <div key={metric.metric} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <span className="font-medium">{metric.metric}</span>
                      <span className="text-2xl font-bold text-primary">
                        {metric.value}%
                      </span>
                    </div>
                    <Progress value={metric.value} />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>AI Cost & Usage</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground">Monthly Cost</p>
                  <p className="text-2xl font-bold">$487</p>
                </div>
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground">Tokens Used</p>
                  <p className="text-2xl font-bold">2.4M</p>
                </div>
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground">Avg Cost/Hire</p>
                  <p className="text-2xl font-bold">$8.50</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

