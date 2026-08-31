import { clearAuthSession, getStoredUser } from "@/lib/auth-storage";

/** Build same-origin API path (via Next.js BFF). */
export function apiPath(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (normalized.startsWith("/api/")) {
    return normalized;
  }
  return `/api${normalized}`;
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const headers = new Headers(options.headers);

  if (
    options.body &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(apiPath(path), {
    ...options,
    headers,
    credentials: "include",
  });

  if (response.status === 401 && typeof window !== "undefined") {
    clearAuthSession();
    if (!window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }

  return response;
}

export async function apiFetchJson<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await apiFetch(path, options);
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    const redirectHint =
      response.status >= 300 && response.status < 400
        ? "The API returned a redirect that could not be resolved. Retry or contact support."
        : null;
    let detail: string | null = null;
    if (typeof body === "object" && body !== null) {
      if ("detail" in body) {
        detail = String((body as { detail: unknown }).detail);
      } else if (
        "error" in body &&
        typeof (body as { error: unknown }).error === "object" &&
        (body as { error: { message?: unknown } }).error?.message
      ) {
        detail = String((body as { error: { message: unknown } }).error.message);
      }
    }
    throw new ApiError(
      detail || redirectHint || response.statusText || "Request failed",
      response.status,
      body
    );
  }

  return body as T;
}

/** @deprecated Use apiFetch('/v1/...') — kept for gradual migration */
export function legacyApiBase(): string {
  return "/api";
}
