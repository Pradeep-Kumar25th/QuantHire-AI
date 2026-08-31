"use client";

import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import {
  CheckCircle2,
  Clock,
  AlertCircle,
  Brain,
  ThumbsUp,
  ThumbsDown,
  MessageSquare,
  Calendar,
  FileText,
  Award,
} from "lucide-react";

const stages = [
  { name: "Applied", status: "completed", date: "Jan 15, 2024" },
  { name: "Screening", status: "completed", date: "Jan 16, 2024" },
  { name: "Assessment", status: "completed", date: "Jan 18, 2024" },
  { name: "Interview", status: "current", date: "In Progress" },
  { name: "Decision", status: "pending", date: "Pending" },
  { name: "Offer", status: "pending", date: "Pending" },
];

export default function ApplicationDetailPage() {
  const params = useParams();
  const appId = params.id as string;

  const application = {
    id: appId,
    candidate: {
      name: "Alice Johnson",
      email: "alice@example.com",
      currentRole: "Senior Software Engineer at TechCorp",
    },
    job: {
      title: "Senior Software Engineer",
      department: "Engineering",
    },
    matchScore: 94,
    appliedDate: "Jan 15, 2024",
    currentStage: "Interview",
    status: "interviewing",
    aiRecommendation: {
      decision: "Strong Hire",
      confidence: 0.89,
      rationale: "Exceptional technical skills with proven track record. Strong culture fit and communication abilities demonstrated in screening. All required competencies present at senior level.",
      strengths: [
        "6+ years relevant experience",
        "Expert Python and FastAPI skills",
        "Strong system design capabilities",
        "Excellent communication in screening",
        "Culture fit indicators strong",
      ],
      concerns: [
        "Limited Kubernetes production experience (learning curve expected)",
      ],
    },
    assessmentScore: 88,
    interviewScores: [
      { interviewer: "Bob Manager", score: 85, type: "Technical", date: "Jan 20" },
      { interviewer: "Sarah Lead", score: 92, type: "Behavioral", date: "Jan 21" },
    ],
  };

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-start gap-4">
          <Avatar className="h-16 w-16">
            <AvatarFallback className="text-xl bg-primary text-primary-foreground">
              AJ
            </AvatarFallback>
          </Avatar>
          <div className="space-y-1">
            <h2 className="text-3xl font-bold">{application.candidate.name}</h2>
            <p className="text-muted-foreground">{application.candidate.currentRole}</p>
            <p className="text-sm text-muted-foreground">
              Applied for: <span className="font-medium">{application.job.title}</span>
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          <Button variant="outline">
            <MessageSquare className="mr-2 h-4 w-4" />
            Chat
          </Button>
          <Button>
            <Calendar className="mr-2 h-4 w-4" />
            Schedule Interview
          </Button>
        </div>
      </div>

      {/* Workflow Progress */}
      <Card>
        <CardHeader>
          <CardTitle>Application Progress</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between">
            {stages.map((stage, index) => (
              <div key={stage.name} className="flex items-center">
                <div className="flex flex-col items-center">
                  <div
                    className={`w-10 h-10 rounded-full flex items-center justify-center ${
                      stage.status === "completed"
                        ? "bg-brand-teal text-white"
                        : stage.status === "current"
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {stage.status === "completed" && (
                      <CheckCircle2 className="h-5 w-5" />
                    )}
                    {stage.status === "current" && (
                      <Clock className="h-5 w-5 animate-pulse" />
                    )}
                    {stage.status === "pending" && <AlertCircle className="h-5 w-5" />}
                  </div>
                  <p className="text-xs font-medium mt-2">{stage.name}</p>
                  <p className="text-xs text-muted-foreground">{stage.date}</p>
                </div>
                {index < stages.length - 1 && (
                  <div
                    className={`h-0.5 w-16 ${
                      stage.status === "completed"
                        ? "bg-brand-teal"
                        : "bg-muted"
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* AI Recommendation */}
      <Card className="border-primary/50 bg-gradient-to-r from-primary/5 to-transparent">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            <CardTitle>AI Recommendation (DecisionAgent)</CardTitle>
            <Badge className="ml-auto bg-brand-teal text-white">
              {application.aiRecommendation.decision}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Confidence Score */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">Confidence Level</span>
              <span className="text-sm font-bold">
                {Math.round(application.aiRecommendation.confidence * 100)}%
              </span>
            </div>
            <Progress
              value={application.aiRecommendation.confidence * 100}
              className="h-2"
            />
          </div>

          {/* AI Rationale */}
          <div className="p-4 rounded-lg bg-background border">
            <p className="text-sm font-medium mb-2">AI Rationale</p>
            <p className="text-sm text-muted-foreground leading-relaxed">
              {application.aiRecommendation.rationale}
            </p>
          </div>

          {/* Strengths & Concerns */}
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <ThumbsUp className="h-4 w-4 text-brand-teal" />
                <p className="text-sm font-medium">Strengths</p>
              </div>
              <ul className="space-y-1">
                {application.aiRecommendation.strengths.map((strength, idx) => (
                  <li key={idx} className="text-sm text-muted-foreground flex items-start">
                    <span className="text-brand-teal mr-2">✓</span>
                    {strength}
                  </li>
                ))}
              </ul>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-brand-gold" />
                <p className="text-sm font-medium">Considerations</p>
              </div>
              <ul className="space-y-1">
                {application.aiRecommendation.concerns.map((concern, idx) => (
                  <li key={idx} className="text-sm text-muted-foreground flex items-start">
                    <span className="text-brand-gold mr-2">!</span>
                    {concern}
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Override */}
          <div className="flex gap-2 pt-2">
            <Button size="sm" variant="secondary">
              <ThumbsUp className="mr-2 h-4 w-4" />
              Agree & Proceed
            </Button>
            <Button size="sm" variant="outline">
              <ThumbsDown className="mr-2 h-4 w-4" />
              Override Decision
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Detailed Scores */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Match Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-primary">
              {application.matchScore}%
            </div>
            <Progress value={application.matchScore} className="mt-2" />
            <p className="text-xs text-muted-foreground mt-2">
              Semantic similarity to job requirements
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Assessment Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-brand-gold">
              {application.assessmentScore}%
            </div>
            <Progress value={application.assessmentScore} className="mt-2" />
            <p className="text-xs text-muted-foreground mt-2">
              Technical assessment performance
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Interview Average</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-brand-teal">
              {Math.round(
                application.interviewScores.reduce((sum, s) => sum + s.score, 0) /
                  application.interviewScores.length
              )}
              %
            </div>
            <Progress
              value={
                application.interviewScores.reduce((sum, s) => sum + s.score, 0) /
                application.interviewScores.length
              }
              className="mt-2"
            />
            <p className="text-xs text-muted-foreground mt-2">
              Average of {application.interviewScores.length} interviews
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="interviews" className="space-y-4">
        <TabsList>
          <TabsTrigger value="interviews">Interviews</TabsTrigger>
          <TabsTrigger value="assessments">Assessments</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="notes">Notes</TabsTrigger>
        </TabsList>

        <TabsContent value="interviews" className="space-y-4">
          {application.interviewScores.map((interview, index) => (
            <Card key={index}>
              <CardContent className="pt-6">
                <div className="flex items-center justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <h4 className="font-semibold">{interview.type} Interview</h4>
                      <Badge variant="outline">{interview.date}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Interviewer: {interview.interviewer}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold">{interview.score}%</div>
                    <Progress value={interview.score} className="w-24 mt-1" />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="assessments">
          <Card>
            <CardHeader>
              <CardTitle>Technical Assessment Results</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="font-medium">Overall Score</span>
                  <span className="text-2xl font-bold text-primary">
                    {application.assessmentScore}%
                  </span>
                </div>
                <Progress value={application.assessmentScore} />
                <div className="pt-4 space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span>Python Coding Challenge</span>
                    <span className="font-medium">95%</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span>System Design</span>
                    <span className="font-medium">85%</span>
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <span>Database Optimization</span>
                    <span className="font-medium">90%</span>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="timeline">
          <Card>
            <CardContent className="pt-6">
              <div className="space-y-4">
                {[
                  {
                    action: "Application submitted",
                    date: "Jan 15, 10:30 AM",
                    icon: FileText,
                  },
                  {
                    action: "AI screening completed (Match: 94%)",
                    date: "Jan 15, 10:32 AM",
                    icon: Brain,
                  },
                  {
                    action: "Resume parsed successfully",
                    date: "Jan 15, 10:33 AM",
                    icon: CheckCircle2,
                  },
                  {
                    action: "Assessment invited",
                    date: "Jan 16, 2:00 PM",
                    icon: Award,
                  },
                  {
                    action: "Assessment completed (Score: 88%)",
                    date: "Jan 18, 4:30 PM",
                    icon: CheckCircle2,
                  },
                  {
                    action: "Interview #1 scheduled",
                    date: "Jan 19, 9:00 AM",
                    icon: Calendar,
                  },
                  {
                    action: "Interview #1 completed (Score: 85%)",
                    date: "Jan 20, 3:00 PM",
                    icon: CheckCircle2,
                  },
                  {
                    action: "Interview #2 completed (Score: 92%)",
                    date: "Jan 21, 11:00 AM",
                    icon: CheckCircle2,
                  },
                ].map((event, index) => (
                  <div key={index} className="flex items-start gap-3">
                    <div className="p-2 rounded-full bg-primary/10">
                      <event.icon className="h-4 w-4 text-primary" />
                    </div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{event.action}</p>
                      <p className="text-xs text-muted-foreground">{event.date}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notes">
          <Card>
            <CardHeader>
              <CardTitle>Recruiter Notes</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="p-4 rounded-lg border bg-muted/50">
                  <div className="flex items-start justify-between mb-2">
                    <p className="text-sm font-medium">Phone Screen Notes</p>
                    <p className="text-xs text-muted-foreground">Jan 16</p>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Excellent communication skills. Very enthusiastic about the role.
                    Strong technical background evident. Asking thoughtful questions
                    about team culture and growth opportunities.
                  </p>
                </div>
                <div className="p-4 rounded-lg border bg-muted/50">
                  <div className="flex items-start justify-between mb-2">
                    <p className="text-sm font-medium">Technical Interview Feedback</p>
                    <p className="text-xs text-muted-foreground">Jan 20</p>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    Solved coding challenge efficiently. Great system design thinking.
                    Would benefit from more Kubernetes exposure but shows strong
                    learning ability.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Next Actions</CardTitle>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Button variant="secondary">
            Move to Offer Stage
          </Button>
          <Button variant="outline" className="border-brand-gold text-brand-gold hover:bg-brand-gold/10">
            Request Additional Interview
          </Button>
          <Button variant="outline" className="text-brand-red border-brand-red hover:bg-brand-red/10">
            Reject Application
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

