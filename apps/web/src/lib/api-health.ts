/**
 * API Health Check Utility — uses same-origin BFF (/api/*).
 */

const API_URL = "/api";

export interface HealthStatus {
  status: string;
  service: string;
  timestamp: string;
  version?: string;
  endpoints?: Record<string, string>;
}

/**
 * Check if backend is healthy and accessible.
 * 
 * @returns Promise<HealthStatus> Health status from backend
 */
export async function checkBackendHealth(): Promise<HealthStatus> {
  const response = await fetch(`${API_URL}/health`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Backend health check failed: HTTP ${response.status}`);
  }
  return response.json();
}

export async function checkBackendHealthV1(): Promise<HealthStatus> {
  const response = await fetch(`${API_URL}/v1/health`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Backend v1 health check failed: HTTP ${response.status}`);
  }
  return response.json();
}

export async function testBackendConnection(): Promise<{
  success: boolean;
  message: string;
  details?: unknown;
}> {
  try {
    const health = await checkBackendHealth();
    const jdReady = await testJdGenerationReady();

    if (!jdReady.success) {
      return {
        success: false,
        message: jdReady.message,
        details: { health, jd: jdReady.details },
      };
    }

    return {
      success: true,
      message: "Backend and JD generator are ready",
      details: { health, jd: jdReady.details },
    };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      success: false,
      message: `Backend health check failed: ${message}`,
      details: {
        error: message,
        healthEndpoint: `${API_URL}/health`,
        suggestion:
          "Verify BFF at /api/health (curl) and redeploy frontend if browser fetch fails while curl succeeds.",
      },
    };
  }
}

export async function testJdGenerationReady(): Promise<{
  success: boolean;
  message: string;
  details?: unknown;
}> {
  try {
    const response = await fetch(`${API_URL}/v1/jd-generation/test`, {
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json" },
    });

    if (response.status === 401) {
      return {
        success: false,
        message: "Sign in required before generating job descriptions",
        details: { status: response.status },
      };
    }

    if (!response.ok) {
      return {
        success: false,
        message: `JD generator check failed: HTTP ${response.status}`,
        details: { status: response.status },
      };
    }

    const payload = (await response.json()) as Record<string, unknown>;
    const llm = payload.llm as Record<string, unknown> | undefined;
    if (llm?.error) {
      return {
        success: false,
        message: `JD generator LLM not configured: ${String(llm.error)}`,
        details: payload,
      };
    }
    if (llm?.azure_openai_configured === false && llm?.openai_api_key_set === false) {
      return {
        success: false,
        message: "JD generator LLM is not configured on the backend",
        details: payload,
      };
    }

    return {
      success: true,
      message: "JD generator endpoint is ready",
      details: payload,
    };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      success: false,
      message: `JD generator check failed: ${message}`,
    };
  }
}

export async function testResumeParsingReady(): Promise<{
  success: boolean;
  message: string;
  details?: unknown;
}> {
  try {
    const response = await fetch(`${API_URL}/v1/resume-parsing/agent-status`, {
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json" },
    });

    if (response.status === 401) {
      return {
        success: false,
        message: "Sign in required before uploading resumes",
        details: { status: response.status },
      };
    }

    if (!response.ok) {
      return {
        success: false,
        message: `Resume parsing check failed: HTTP ${response.status}`,
        details: { status: response.status },
      };
    }

    const payload = (await response.json()) as Record<string, unknown>;
    if (payload.llm_available === false) {
      return {
        success: false,
        message: "Resume parsing LLM is not configured on the backend",
        details: payload,
      };
    }
    if (payload.document_intelligence_available === false) {
      return {
        success: false,
        message: "Azure Document Intelligence is not configured for resume extraction",
        details: payload,
      };
    }
    if (payload.status !== "ACTIVE" && payload.agent_active === false) {
      return {
        success: false,
        message: "Resume parsing agent is not active",
        details: payload,
      };
    }

    return {
      success: true,
      message: "Resume parsing pipeline is ready",
      details: payload,
    };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      success: false,
      message: `Resume parsing check failed: ${message}`,
    };
  }
}

export async function testJobMatchingReady(): Promise<{
  success: boolean;
  message: string;
  details?: unknown;
}> {
  try {
    const response = await fetch(`${API_URL}/v1/job-matching/health`, {
      cache: "no-store",
      credentials: "include",
      headers: { Accept: "application/json" },
    });

    if (response.status === 401) {
      return {
        success: false,
        message: "Sign in required before launching HSS-D matching",
        details: { status: response.status },
      };
    }

    if (!response.ok) {
      return {
        success: false,
        message: `HSS-D health check failed: HTTP ${response.status}`,
        details: { status: response.status },
      };
    }

    const payload = (await response.json()) as Record<string, unknown>;
    if (payload.status !== "ok" || payload.llm_available === false) {
      return {
        success: false,
        message:
          typeof payload.error === "string"
            ? payload.error
            : "HSS-D matching swarm is not ready",
        details: payload,
      };
    }

    return {
      success: true,
      message: "HSS-D job matching swarm is ready",
      details: payload,
    };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : String(error);
    return {
      success: false,
      message: `HSS-D readiness check failed: ${message}`,
    };
  }
}

