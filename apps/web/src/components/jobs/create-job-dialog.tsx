"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { apiFetchJson } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface CreateJobDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onJobCreated?: () => void;
}

export function CreateJobDialog({ open, onOpenChange, onJobCreated }: CreateJobDialogProps) {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    level: "",
    department: "",
    location: "",
    description: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      // Call API to create job
      const result = await apiFetchJson<{ success?: boolean }>("/v1/jobs", {
        method: "POST",
        body: JSON.stringify(formData),
      });

      if (result.success !== false) {
        // Reset form
        setFormData({
          title: "",
          level: "",
          department: "",
          location: "",
          description: "",
        });
        
        // Close dialog and refresh jobs list
        onOpenChange(false);
        if (onJobCreated) {
          onJobCreated();
        }
      } else {
        console.error('Failed to create job:', result);
        alert('Failed to create job. Please try again.');
      }
    } catch (error) {
      console.error('Error creating job:', error);
      alert('Error creating job. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Create New Job</DialogTitle>
          <DialogDescription>
            AI will help generate a structured job specification from your description.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="title">Job Title</Label>
              <Input
                id="title"
                placeholder="e.g., Senior Software Engineer"
                value={formData.title}
                onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                required
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="level">Level</Label>
                <Input 
                  id="level" 
                  placeholder="e.g., Senior"
                  value={formData.level}
                  onChange={(e) => setFormData({ ...formData, level: e.target.value })}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="department">Department</Label>
                <Input 
                  id="department" 
                  placeholder="e.g., Engineering"
                  value={formData.department}
                  onChange={(e) => setFormData({ ...formData, department: e.target.value })}
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="location">Location</Label>
              <Input 
                id="location" 
                placeholder="e.g., San Francisco, CA"
                value={formData.location}
                onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="description">Job Description</Label>
              <Textarea
                id="description"
                placeholder="Describe the role, responsibilities, and requirements..."
                rows={6}
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                required
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? "Creating..." : "Create Job"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

