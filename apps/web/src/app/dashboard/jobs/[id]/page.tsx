"use client";

import { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetchJson } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  MapPin,
  DollarSign,
  Users,
  Calendar,
  TrendingUp,
  Brain,
  Sparkles,
  Trash2,
} from "lucide-react";
import { MatchedCandidatesView } from "@/components/jobs/matched-candidates-view";
import { ApplicationsTimeline } from "@/components/jobs/applications-timeline";
import { EditJobDialog } from "@/components/jobs/edit-job-dialog";
import { JDGenerationDialog } from "@/components/jobs/jd-generation-dialog";
import { ConfirmDeleteDialog } from "@/components/ui/confirm-delete-dialog";
import { jobHasEnterpriseJd } from "@/lib/jd-persist";
import { api } from "@/lib/api";
import { deleteJobWithConfirm } from "@/lib/delete-resource";

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showJdEditor, setShowJdEditor] = useState(false);
  const [job, setJob] = useState<any>(null);

  useEffect(() => {
    // Fetch job data from API
    const fetchJob = async () => {
      try {
        const data = await apiFetchJson<any>(`/v1/jobs/${jobId}`);
        setJob(data);
      } catch (error) {
        console.error("Failed to fetch job:", error);
      }
    };

    if (jobId) {
      fetchJob();
    }
  }, [jobId]);

  const handleJobUpdated = () => {
    setShowEditDialog(false);
    // Refetch job data
    const fetchJob = async () => {
      try {
        const data = await apiFetchJson<any>(`/v1/jobs/${jobId}`);
        setJob(data);
      } catch (error) {
        console.error("Failed to fetch job:", error);
      }
    };
    fetchJob();
  };

  // Mock data fallback with default values
  const defaultJob = {
    id: jobId,
    title: "Senior Software Engineer",
    department: "Engineering",
    level: "Senior",
    location: "San Francisco, CA",
    remote: true,
    status: "open",
    description: `We're seeking an experienced Senior Software Engineer to join our growing engineering team. You'll be working on cutting-edge AI-powered products, building scalable backend systems, and mentoring junior engineers.`,
    responsibilities: [
      "Lead design and development of microservices architecture",
      "Mentor junior and mid-level engineers",
      "Collaborate with product team on technical requirements",
      "Optimize database performance and API latency",
      "Contribute to technical strategy and architecture decisions",
    ],
    requirements: [
      "5+ years of software engineering experience",
      "Expert-level Python and FastAPI knowledge",
      "Strong experience with PostgreSQL and distributed systems",
      "Kubernetes and cloud infrastructure experience",
      "Excellent communication and leadership skills",
    ],
    skills: [
      { name: "Python", required: true, level: "Expert" },
      { name: "FastAPI", required: true, level: "Advanced" },
      { name: "PostgreSQL", required: true, level: "Intermediate" },
      { name: "Docker", required: false, level: "Intermediate" },
      { name: "Kubernetes", required: false, level: "Beginner" },
    ],
    compensation: {
      min: 140000,
      max: 180000,
      currency: "USD",
      equity: true,
    },
    openings: 2,
    filled: 1,
    applications: 45,
    created: "2024-01-15",
  };

  const displayJob = job 
    ? { ...defaultJob, ...job }  // API data takes precedence
    : defaultJob;  // Use fallback if no API data

  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const refetchJob = async () => {
    try {
      const data = await apiFetchJson<any>(`/v1/jobs/${jobId}`);
      setJob(data);
    } catch (error) {
      console.error("Failed to fetch job:", error);
    }
  };

  const handleDeleteJob = () => {
    setShowDeleteDialog(true);
  };

  const executeDeleteJob = async () => {
    try {
      setIsDeleting(true);
      await api.jobs.delete(jobId);
      if (typeof window !== "undefined") {
        sessionStorage.removeItem(`quanthire:jd-draft-${jobId}`);
        localStorage.removeItem(`quanthire:jd-draft-${jobId}`);
      }
      setShowDeleteDialog(false);
      router.push("/dashboard/jobs");
    } catch (error: any) {
      const status = error?.response?.status;
      if (status === 204 || status === 200 || status === 404) {
        if (typeof window !== "undefined") {
          sessionStorage.removeItem(`quanthire:jd-draft-${jobId}`);
          localStorage.removeItem(`quanthire:jd-draft-${jobId}`);
        }
        setShowDeleteDialog(false);
        router.push("/dashboard/jobs");
      } else {
        console.error("Failed to delete job:", error);
        setShowDeleteDialog(false);
        router.push("/dashboard/jobs");
      }
    } finally {
      setIsDeleting(false);
    }
  };

  const hasEnterpriseJd = job ? jobHasEnterpriseJd(job) : false;

  return (
    <div className="flex-1 space-y-6 p-8 pt-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-3">
            <h2 className="text-3xl font-bold tracking-tight">{displayJob.title}</h2>
            <Badge
              className={
                displayJob.status === "open"
                  ? "bg-brand-teal text-white"
                  : "bg-brand-gray text-brand-dark"
              }
            >
              {displayJob.status}
            </Badge>
          </div>
          <p className="text-muted-foreground">
            {displayJob.department} • {displayJob.level} Level
          </p>
        </div>
        <div className="flex gap-2">
          {hasEnterpriseJd && (
            <Button variant="default" onClick={() => setShowJdEditor(true)}>
              <Sparkles className="mr-2 h-4 w-4" />
              Edit AI JD
            </Button>
          )}
          <Button 
            variant="outline" 
            onClick={() => setShowEditDialog(true)}
          >
            Edit Job
          </Button>
          <Button
            variant="outline"
            className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
            onClick={() => void handleDeleteJob()}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            Delete Job
          </Button>
          <Button>
            <Brain className="mr-2 h-4 w-4" />
            AI Match Candidates
          </Button>
        </div>
      </div>

      {/* Edit Job Dialog */}
      <EditJobDialog
        open={showEditDialog}
        onOpenChange={setShowEditDialog}
        job={displayJob}
        onJobUpdated={handleJobUpdated}
      />

      <JDGenerationDialog
        open={showJdEditor}
        onOpenChange={setShowJdEditor}
        editJobId={jobId}
        onJDGenerated={() => {
          void refetchJob();
        }}
      />

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Applications</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{displayJob.applications}</div>
            <p className="text-xs text-muted-foreground">
              +12 this week
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Openings</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {displayJob.filled}/{displayJob.openings}
            </div>
            <p className="text-xs text-muted-foreground">positions filled</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Location</CardTitle>
            <MapPin className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">{displayJob.location}</div>
            <p className="text-xs text-muted-foreground">
              {displayJob.remote && "Remote available"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Compensation</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-lg font-bold">
              ${(displayJob.compensation.min / 1000).toFixed(0)}K - $
              {(displayJob.compensation.max / 1000).toFixed(0)}K
            </div>
            <p className="text-xs text-muted-foreground">
              {displayJob.compensation.equity && "+ Equity"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabbed Content */}
      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="candidates">
            AI-Matched Candidates ({displayJob.applications})
          </TabsTrigger>
          <TabsTrigger value="applications">Applications Timeline</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            {/* Description */}
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>Job Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground leading-relaxed">
                  {displayJob.description}
                </p>
              </CardContent>
            </Card>

            {/* Responsibilities */}
            <Card>
              <CardHeader>
                <CardTitle>Responsibilities</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {displayJob.responsibilities.map((item: string, index: number) => (
                    <li key={index} className="flex items-start">
                      <span className="mr-2 text-primary">•</span>
                      <span className="text-sm text-muted-foreground">{item}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            {/* Requirements */}
            <Card>
              <CardHeader>
                <CardTitle>Requirements</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {displayJob.requirements.map((item: string, index: number) => (
                    <li key={index} className="flex items-start">
                      <span className="mr-2 text-primary">•</span>
                      <span className="text-sm text-muted-foreground">{item}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            {/* Skills Matrix */}
            <Card className="md:col-span-2">
              <CardHeader>
                <CardTitle>Skills Matrix (AI-Generated)</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {displayJob.skills.map((skill: { name: string; required?: boolean; level: string }) => (
                    <Badge
                      key={skill.name}
                      variant={skill.required ? "default" : "outline"}
                      className="text-sm py-1 px-3"
                    >
                      {skill.name} - {skill.level}
                      {skill.required && " ⭐"}
                    </Badge>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="candidates">
          <MatchedCandidatesView jobId={jobId} />
        </TabsContent>

        <TabsContent value="applications">
          <ApplicationsTimeline jobId={jobId} />
        </TabsContent>

        <TabsContent value="analytics">
          <Card>
            <CardHeader>
              <CardTitle>Job Analytics</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-muted-foreground">
                Analytics dashboard coming soon...
              </p>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
      <ConfirmDeleteDialog
        open={showDeleteDialog}
        onOpenChange={setShowDeleteDialog}
        title={`Delete "${displayJob.title}"?`}
        description="This removes the job listing and its indexed JD from QuantChat and matching. This cannot be undone."
        warningNote={
          (displayJob.applications ?? 0) > 0
            ? `Note: This job currently has ${displayJob.applications} active application(s).`
            : undefined
        }
        confirmLabel="Delete Job"
        cancelLabel="Cancel"
        onConfirm={executeDeleteJob}
        isDeleting={isDeleting}
      />
    </div>
  );
}
