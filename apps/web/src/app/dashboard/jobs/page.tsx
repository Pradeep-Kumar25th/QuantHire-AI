"use client";

import { useState, useEffect } from "react";
import { apiFetchJson } from "@/lib/api-client";
import { Plus, Search, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { JobCard } from "@/components/jobs/job-card";
import { CreateJobDialog } from "@/components/jobs/create-job-dialog";
import { EditJobDialog } from "@/components/jobs/edit-job-dialog";
import { JDGenerationDialog } from "@/components/jobs/jd-generation-dialog";
import { jobHasEnterpriseJd } from "@/lib/jd-persist";
import { buildJobCardPreviewFromJob } from "@/lib/job-card-preview";
import { deleteJobWithConfirm } from "@/lib/delete-resource";

import { ConfirmDeleteDialog } from "@/components/ui/confirm-delete-dialog";
import { api } from "@/lib/api";

interface Job {
  id: string;
  title: string;
  department: string;
  location: string;
  remote: boolean;
  status: string;
  openings: number;
  filled: number;
  applications: number;
  created: string;
  description?: string;
  requirements?: string[];
  hasEnterpriseJd?: boolean;
  preview?: ReturnType<typeof buildJobCardPreviewFromJob>;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [showEditDialog, setShowEditDialog] = useState(false);
  const [showJDGenerationDialog, setShowJDGenerationDialog] = useState(false);
  const [editJobId, setEditJobId] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [jobToDelete, setJobToDelete] = useState<Job | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const data = await apiFetchJson<any[]>("/v1/jobs");

      // Transform backend job format to frontend format
      const transformedJobs = (Array.isArray(data) ? data : []).map((job: any) => {
        const preview = buildJobCardPreviewFromJob(job);
        return {
          id: job.id,
          title: preview.title,
          department: preview.departmentDisplay,
          location: preview.locationLabel,
          remote: preview.remote,
          status: job.status || "draft",
          openings: job.openings_count || 1,
          filled: job.filled_count || 0,
          applications: 0, // TODO: Get from backend
          created: job.created_at || new Date().toISOString(),
          description: job.description,
          requirements: job.requirements,
          hasEnterpriseJd: jobHasEnterpriseJd(job),
          preview,
        };
      });

      setJobs(transformedJobs);
    } catch (error) {
      console.error('Error fetching jobs:', error);
      // Use empty array instead of dummy data
      setJobs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();

    // Listen for job updates
    const handleJobsUpdated = () => {
      fetchJobs();
    };

    window.addEventListener('jobsUpdated', handleJobsUpdated);

    return () => {
      window.removeEventListener('jobsUpdated', handleJobsUpdated);
    };
  }, []);

  const filteredJobs = jobs.filter(job =>
    job.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    job.department.toLowerCase().includes(searchTerm.toLowerCase()) ||
    job.location.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleJobCreated = () => {
    fetchJobs();
    setShowCreateDialog(false);
  };

  const handleOpenNewJdDialog = () => {
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("quanthire:jd-draft-job-id");
    }
    setEditJobId(null);
    setShowJDGenerationDialog(true);
  };

  const handleOpenSavedJd = (jobId: string) => {
    setEditJobId(jobId);
    setShowJDGenerationDialog(true);
  };

  const handleJdDialogOpenChange = (open: boolean) => {
    setShowJDGenerationDialog(open);
    if (!open) {
      setEditJobId(null);
    }
  };

  const handleJobEdit = (job: Job) => {
    setSelectedJob(job);
    setShowEditDialog(true);
  };

  const handleJobUpdated = () => {
    fetchJobs();
    setShowEditDialog(false);
    setSelectedJob(null);
  };

  const handleDeleteJob = (job: Job) => {
    setJobToDelete(job);
  };

  const executeDeleteJob = async () => {
    if (!jobToDelete) return;
    try {
      setIsDeleting(true);
      await api.jobs.delete(jobToDelete.id);
      if (typeof window !== "undefined") {
        sessionStorage.removeItem(`quanthire:jd-draft-${jobToDelete.id}`);
        localStorage.removeItem(`quanthire:jd-draft-${jobToDelete.id}`);
      }
      setJobToDelete(null);
      await fetchJobs();
    } catch (error: any) {
      const status = error?.response?.status;
      if (status === 204 || status === 200 || status === 404) {
        if (typeof window !== "undefined") {
          sessionStorage.removeItem(`quanthire:jd-draft-${jobToDelete.id}`);
          localStorage.removeItem(`quanthire:jd-draft-${jobToDelete.id}`);
        }
        setJobToDelete(null);
        await fetchJobs();
      } else {
        console.error("Failed to delete job:", error);
        setJobToDelete(null);
        await fetchJobs();
      }
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="flex-1 space-y-4 p-8 pt-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Jobs</h2>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setShowCreateDialog(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Job
          </Button>
          <Button onClick={handleOpenNewJdDialog}>
            <Sparkles className="mr-2 h-4 w-4" />
            AI Generate JD
          </Button>
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <div className="relative flex-1">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search jobs..."
            className="pl-8"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="text-center">
            <p className="text-muted-foreground">Loading jobs...</p>
          </div>
        </div>
      ) : filteredJobs.length === 0 ? (
        <div className="flex justify-center items-center h-64 rounded-xl border border-dashed bg-muted/20">
          <div className="text-center space-y-2">
            <p className="text-muted-foreground">No jobs match your search.</p>
            <Button variant="outline" onClick={() => setSearchTerm("")}>
              Clear search
            </Button>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredJobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onEdit={handleJobEdit}
              onOpenJd={handleOpenSavedJd}
              onDelete={handleDeleteJob}
            />
          ))}
        </div>
      )}

      <CreateJobDialog
        open={showCreateDialog}
        onOpenChange={setShowCreateDialog}
        onJobCreated={handleJobCreated}
      />

      <EditJobDialog
        open={showEditDialog}
        onOpenChange={setShowEditDialog}
        job={selectedJob}
        onJobUpdated={handleJobUpdated}
      />

      <JDGenerationDialog
        open={showJDGenerationDialog}
        onOpenChange={handleJdDialogOpenChange}
        onJDGenerated={handleJobCreated}
        editJobId={editJobId}
      />

      <ConfirmDeleteDialog
        open={!!jobToDelete}
        onOpenChange={(open) => !open && setJobToDelete(null)}
        title={`Delete "${jobToDelete?.preview?.title || jobToDelete?.title || 'Job'}"?`}
        description="This removes the job listing and its indexed JD from QuantChat and matching. This cannot be undone."
        warningNote={
          (jobToDelete?.applications ?? 0) > 0
            ? `Note: This job currently has ${jobToDelete?.applications} active application(s).`
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

