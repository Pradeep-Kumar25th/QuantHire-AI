/**
 * React hooks for candidate operations
 */

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface Candidate {
  id: string;
  name: string;
  email: string;
  phone?: string;
  location?: string;
  profile_json: Record<string, unknown>;
  parsing_confidence?: number;
  missing_fields: string[];
  source?: string;
  is_active: boolean;
  created_at?: string;
}

export function useCandidates() {
  return useQuery({
    queryKey: ["candidates"],
    queryFn: async () => {
      const response = await api.candidates.list();
      return response.data;
    },
  });
}

export function useCandidate(id: string) {
  return useQuery({
    queryKey: ["candidates", id],
    queryFn: async () => {
      const response = await api.candidates.get(id);
      return response.data as Candidate;
    },
    enabled: Boolean(id && id !== "undefined"),
  });
}

export function useUploadResume() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (file: File) => {
      const response = await api.candidates.upload(file);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["candidates"] });
    },
  });
}

