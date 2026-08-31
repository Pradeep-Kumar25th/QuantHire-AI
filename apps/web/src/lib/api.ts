import axios, { AxiosInstance } from "axios";

import { clearAuthSession } from "@/lib/auth-storage";

/** Same-origin BFF base — browser never calls backend URL directly. */
const API_URL = "/api";

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
  timeout: 600000, // 10 minutes for long-running operations like JD generation
});

// Log API configuration for debugging
console.log('🔧 API Client Configuration:', {
  baseURL: API_URL,
  fullJDGenerationURL: `${API_URL}/v1/jd-generation/generate`,
});

// Request interceptor — session JWT is HttpOnly cookie (withCredentials: true)
apiClient.interceptors.request.use(
  (config) => config,
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    console.log('✅ API Response:', {
      status: response.status,
      url: response.config.url,
      method: response.config.method,
    });
    return response;
  },
  (error) => {
    // Log all errors for debugging
    console.error('❌ API Response Interceptor Error:', {
      message: error.message,
      code: error.code,
      hasResponse: !!error.response,
      status: error.response?.status,
      statusText: error.response?.statusText,
      data: error.response?.data,
      url: error.config?.url,
      baseURL: error.config?.baseURL,
      errorStatus: error.status,
      errorObject: error,
    });
    
    if (error.response?.status === 401) {
      clearAuthSession();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
    }
    // Preserve error structure - don't modify it
    return Promise.reject(error);
  }
);

// API functions
export const api = {
  // Jobs
  jobs: {
    list: () => apiClient.get("/v1/jobs"),
    get: (id: string) => apiClient.get(`/v1/jobs/${id}`),
    create: (data: any) => apiClient.post("/v1/jobs", data),
    update: (id: string, data: any) => apiClient.put(`/v1/jobs/${id}`, data),
    delete: (id: string) =>
      apiClient.delete(`/v1/jobs/${id}`, {
        validateStatus: (status) => status === 204 || (status >= 200 && status < 300),
      }),
    publish: (id: string) => apiClient.post(`/v1/jobs/${id}/publish`),
    match: (id: string, top: number = 10) =>
      apiClient.post(`/v1/jobs/${id}/match?top=${top}`),
  },

  // JD Generation (Autonomous AI Agents)
  jdGeneration: {
    // Test endpoint to verify connectivity
    test: () => {
      const fullUrl = `${API_URL}/v1/jd-generation/test`;
      console.log('🧪 Testing JD Generation endpoint:', fullUrl);
      return apiClient.get("/v1/jd-generation/test").then(response => {
        console.log('✅ JD Generation test endpoint accessible:', response.data);
        return response;
      }).catch(error => {
        console.error('❌ JD Generation test endpoint failed:', {
          url: fullUrl,
          error: error.message,
          code: error.code,
          response: error.response ? {
            status: error.response.status,
            data: error.response.data,
          } : null,
        });
        throw error;
      });
    },
    // Save JD to vector store (pgvector on Azure, Milvus locally)
    save: (data: {
      job_id?: string;
      job_title: string;
      department: string;
      job_description: any;
    }) => {
      console.log('💾 Saving JD to vector store:', data);
      return apiClient.post("/v1/jd-generation/save", data);
    },
    generate: (data: {
      job_id?: string;
      job_title: string;
      job_level?: string;
      department: string;
      years_of_experience?: string;
      internal_title?: string;
      business_unit?: string;
      qualification?: string;
      skills?: string;
      location?: string;
      remote_allowed?: boolean;
      user_requirements?: string;
      user_edits?: Record<string, any>;
    }) => {
      console.log('🚀 JD Generation Request:', {
        url: `${API_URL}/v1/jd-generation/generate`,
        data,
      });
      const fullUrl = `${API_URL}/v1/jd-generation/generate`;
      console.log('📡 Making JD Generation request to:', fullUrl);
      console.log('📦 Request payload:', JSON.stringify(data, null, 2));
      
      return apiClient.post("/v1/jd-generation/generate", data, {
        timeout: 600000, // 10 minutes timeout for JD generation (AI agents can take 5+ minutes)
        validateStatus: function (status) {
          // Accept all status codes - we'll handle errors manually
          return status >= 200 && status < 600;
        },
      }).then(response => {
        console.log('📥 Received response:', {
          status: response.status,
          statusText: response.statusText,
          hasData: !!response.data,
          dataKeys: response.data ? Object.keys(response.data) : [],
        });
        
        // Check if response is successful
        if (response.status >= 200 && response.status < 300) {
          console.log('✅ JD Generation request successful:', response.status);
          return response;
        } else {
          // Non-2xx status - create error object with proper structure
          const error: any = new Error(`Request failed with status ${response.status}: ${response.statusText || 'Unknown error'}`);
          // Ensure error object has response property (axios format)
          error.response = {
            status: response.status,
            statusText: response.statusText,
            data: response.data,
            headers: response.headers,
            config: response.config,
          };
          error.status = response.status;
          error.code = 'HTTP_ERROR';
          error.config = response.config;
          error.request = response.request;
          // Ensure response is a full axios response object
          error.response = response;
          console.error('❌ HTTP Error Response (Throwing):', {
            status: response.status,
            statusText: response.statusText,
            data: response.data,
            errorHasResponse: !!error.response,
            errorResponseStatus: error.response?.status,
            errorStatus: error.status,
            errorObject: {
              message: error.message,
              status: error.status,
              code: error.code,
              hasResponse: !!error.response,
            },
          });
          throw error;
        }
      }).catch(error => {
        console.error('❌ JD Generation request failed:', {
          url: fullUrl,
          error: error.message,
          code: error.code,
          name: error.name,
          hasResponse: !!error.response,
          response: error.response ? {
            status: error.response.status,
            statusText: error.response.statusText,
            data: error.response.data,
            headers: error.response.headers,
          } : null,
          request: error.request ? {
            exists: true,
            readyState: error.request.readyState,
          } : null,
        });
        throw error;
      });
    },
    generateAsync: (data: {
      job_id?: string;
      job_title: string;
      job_level?: string;
      department: string;
      years_of_experience?: string;
      internal_title?: string;
      business_unit?: string;
      qualification?: string;
      skills?: string;
      location?: string;
      remote_allowed?: boolean;
      user_requirements?: string;
      user_edits?: Record<string, any>;
    }) => {
      return apiClient.post("/v1/jd-generation/generate-async", data, {
        timeout: 60_000,
      });
    },
    getGenerationStatus: (taskId: string) => {
      return apiClient.get(`/v1/jd-generation/generate-status/${taskId}`, {
        timeout: 30_000,
      });
    },
    pollGeneration: async (
      taskId: string,
      options?: {
        intervalMs?: number;
        maxAttempts?: number;
        onStatus?: (status: string, attempt: number) => void;
      }
    ) => {
      const intervalMs = options?.intervalMs ?? 3000;
      const maxAttempts = options?.maxAttempts ?? 200;
      for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
        if (attempt > 0) {
          await new Promise((resolve) => setTimeout(resolve, intervalMs));
        }
        const response = await apiClient.get(
          `/v1/jd-generation/generate-status/${taskId}`,
          { timeout: 30_000 }
        );
        const payload = response.data;
        options?.onStatus?.(payload.status, attempt + 1);
        if (payload.status === "completed" && payload.result) {
          return payload.result;
        }
        if (payload.status === "failed") {
          throw new Error(payload.error || "JD generation failed");
        }
      }
      throw new Error(
        "JD generation is taking longer than expected. Check the Jobs list for a new draft."
      );
    },
  },

  // Job Matching (Hierarchical Specialist Swarm with Debate)
  jobMatching: {
    listCandidates: () => apiClient.get("/v1/job-matching/candidates"),
    listJDs: () => apiClient.get("/v1/job-matching/jds"),
    health: () => apiClient.get("/v1/job-matching/health"),
    match: (data: {
      candidate_id: string;
      jd_id: string;
      weights?: Record<string, number>;
    }) =>
      apiClient.post("/v1/job-matching/match", data, {
        timeout: 600000,
      }),
    rank: (data: {
      jd_id: string;
      candidate_ids?: string[];
      weights?: Record<string, number>;
      max_concurrency?: number;
    }) =>
      apiClient.post("/v1/job-matching/rank", data, {
        timeout: 600000,
      }),
    streamUrl: (
      candidate_id: string,
      jd_id: string,
      weights?: Record<string, number>,
    ) => {
      const params = new URLSearchParams({ candidate_id, jd_id });
      if (weights && Object.keys(weights).length > 0) {
        params.set("weights", JSON.stringify(weights));
      }
      return `${API_URL}/v1/job-matching/match-stream?${params.toString()}`;
    },
  },

  // QuantChat AI (Hybrid Architecture) - Backward compatible with old /api/chat
  quantchat: {
    chat: (data: { message: string; user_id?: string }) =>
      apiClient.post("/v1/quantchat/chat", data),
    status: () => apiClient.get("/v1/quantchat/status"),
  },

  // Agent Observability (live metrics from the RAG pipeline)
  observability: {
    dashboard: () => apiClient.get("/v1/quantchat/observability/dashboard"),
    performance: () => apiClient.get("/v1/quantchat/observability/performance"),
    quality: () => apiClient.get("/v1/quantchat/observability/quality"),
    cost: () => apiClient.get("/v1/quantchat/observability/cost"),
    decisions: (limit = 50) => apiClient.get(`/v1/quantchat/observability/decisions?limit=${limit}`),
    alerts: (unacknowledgedOnly = false) => apiClient.get(`/v1/quantchat/observability/alerts?unacknowledged_only=${unacknowledgedOnly}`),
    acknowledgeAlert: (alertId: string) => apiClient.post(`/v1/quantchat/observability/alerts/${alertId}/acknowledge`),
    feedback: () => apiClient.get("/v1/quantchat/observability/feedback"),
    health: () => apiClient.get("/v1/quantchat/observability/health"),
    exportTraces: (limit = 500) => apiClient.get(`/v1/quantchat/observability/traces/export?limit=${limit}`),
    submitFeedback: (data: { trace_id: string; rating: "positive" | "negative" | "neutral"; comment?: string }) =>
      apiClient.post("/v1/quantchat/feedback", data),
  },

  // Resume Parsing (Hybrid Architecture + Autonomous AI Agent) - Backward compatible
  resumeParsing: {
    upload: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiClient.post("/v1/resume-parsing/upload", formData);
    },
    analyze: (data: { resume_text: string; candidate_name?: string }) =>
      apiClient.post("/v1/resume-parsing/analyze", data),  // New endpoint: /api/v1/resume-parsing/analyze (also works with /api/resume-analysis)
    getCandidates: () => apiClient.get("/v1/resume-parsing/candidates"),  // New endpoint: /api/v1/resume-parsing/candidates (also works with /api/candidates)
    getCandidate: (id: string) => apiClient.get(`/v1/resume-parsing/candidate/${id}`),  // New endpoint: /api/v1/resume-parsing/candidate/{id}
    getAgentStatus: () => apiClient.get("/v1/resume-parsing/agent-status"),  // New endpoint: /api/v1/resume-parsing/agent-status
  },

  // Candidates
  candidates: {
    list: (params?: { is_active?: boolean }) =>
      apiClient.get("/v1/candidates", { params: params ?? { is_active: true } }),
    get: (id: string) => apiClient.get(`/v1/candidates/${id}`),
    create: (data: any) => apiClient.post("/v1/candidates", data),
    upload: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiClient.post("/v1/candidates/upload", formData);
    },
    update: (id: string, data: any) =>
      apiClient.put(`/v1/candidates/${id}`, data),
    delete: (id: string) =>
      apiClient.delete(`/v1/candidates/${id}`, {
        validateStatus: (status) => status === 204 || (status >= 200 && status < 300),
      }),
  },

  // Applications
  applications: {
    list: (filters?: any) =>
      apiClient.get("/v1/applications", { params: filters }),
    get: (id: string) => apiClient.get(`/v1/applications/${id}`),
    create: (data: any) => apiClient.post("/v1/applications", data),
    updateStatus: (id: string, status: string) =>
      apiClient.patch(`/v1/applications/${id}/status`, { status }),
  },
};
