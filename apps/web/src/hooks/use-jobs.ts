/**
 * React hooks for job operations
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface Job {
  id: string;
  title: string;
  level: string;
  department: string;
  location?: string;
  remote_allowed: boolean;
  status: string;
  description: string;
  spec_json: any;
  openings_count: number;
  filled_count: number;
}

export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: async () => {
      const response = await api.jobs.list();
      return response.data;
    },
  });
}

export function useJob(id: string) {
  return useQuery({
    queryKey: ["jobs", id],
    queryFn: async () => {
      const response = await api.jobs.get(id);
      return response.data;
    },
    enabled: !!id,
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: {
      title: string;
      level: string;
      department: string;
      location?: string;
      description: string;
    }) => {
      const response = await api.jobs.create(data);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
}

export function useMatchCandidates(jobId: string) {
  return useMutation({
    mutationFn: async (top: number = 10) => {
      const response = await api.jobs.match(jobId, top);
      return response.data;
    },
  });
}

