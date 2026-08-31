"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { apiFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

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
}

interface EditJobDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  job: Job | null;
  onJobUpdated: () => void;
}

export function EditJobDialog({ open, onOpenChange, job, onJobUpdated }: EditJobDialogProps) {
  const [formData, setFormData] = useState({
    title: job?.title || "",
    department: job?.department || "",
    location: job?.location || "",
    remote: job?.remote || false,
    status: job?.status || "open",
    openings: job?.openings || 1,
    description: job?.description || "",
    requirements: (job?.requirements || []).join("\n")
  });

  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!job) return;

    setLoading(true);
    try {
      const requirementsArray = formData.requirements
        .split('\n')
        .filter(req => req.trim().length > 0);

      const response = await apiFetch(`/v1/jobs/${job.id}`, {
        method: "PUT",
        body: JSON.stringify({
          ...formData,
          requirements: requirementsArray,
          type: "full-time",
        }),
      });

      if (response.ok) {
        onJobUpdated();
        onOpenChange(false);
      } else {
        console.error('Failed to update job');
      }
    } catch (error) {
      console.error('Error updating job:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Edit Job</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <Label htmlFor="title">Job Title</Label>
            <Input
              id="title"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="department">Department</Label>
              <Input
                id="department"
                value={formData.department}
                onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                required
              />
            </div>
            <div>
              <Label htmlFor="location">Location</Label>
              <Input
                id="location"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
                required
              />
            </div>
          </div>

          <div>
            <Label htmlFor="description">Job Description</Label>
            <Textarea
              id="description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={5}
              placeholder="Enter job description..."
            />
          </div>

          <div>
            <Label htmlFor="requirements">Requirements (one per line)</Label>
            <Textarea
              id="requirements"
              value={formData.requirements}
              onChange={(e) => setFormData({ ...formData, requirements: e.target.value })}
              rows={4}
              placeholder="Enter requirements, one per line..."
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="openings">Openings</Label>
              <Input
                id="openings"
                type="number"
                min="1"
                value={formData.openings}
                onChange={(e) => setFormData({ ...formData, openings: parseInt(e.target.value) || 1 })}
                required
              />
            </div>
            <div>
              <Label htmlFor="status">Status</Label>
              <select
                id="status"
                value={formData.status}
                onChange={(e) => setFormData({ ...formData, status: e.target.value })}
                className="w-full h-10 px-3 border rounded-md"
              >
                <option value="open">Open</option>
                <option value="closed">Closed</option>
                <option value="draft">Draft</option>
              </select>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <input
              id="remote"
              type="checkbox"
              checked={formData.remote}
              onChange={(e) => setFormData({ ...formData, remote: e.target.checked })}
              className="h-4 w-4"
            />
            <Label htmlFor="remote">Remote Position</Label>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "Saving..." : "Save Changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

