import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

/**
 * BFF proxy: browser → same-origin /api/* → FastAPI backend.
 */

function backendBaseUrl(): string {
  const env = process.env as Record<string, string | undefined>;
  const raw =
    env["BFF_BACKEND_URL"] ||
    env["BACKEND_INTERNAL_URL"] ||
    env["BACKEND_URL"] ||
    env["INTERNAL_API_URL"] ||
    env["NEXT_PUBLIC_API_URL"] ||
    "http://localhost:8000";
  let cleaned = raw.replace(/\/+$/, "");
  if (cleaned.endsWith("/api")) {
    cleaned = cleaned.slice(0, -4);
  }
  return cleaned || "http://localhost:8000";
}

const FORWARD_REQUEST_HEADERS = [
  "authorization",
  "cookie",
  "content-type",
  "accept",
  "accept-language",
  "x-correlation-id",
  "x-request-id",
  "content-length",
];

// Node fetch decompresses the backend body — never forward content-encoding.
const FORWARD_RESPONSE_HEADERS = [
  "content-type",
  "content-disposition",
  "cache-control",
  "etag",
  "set-cookie",
  "x-accel-buffering",
  "x-correlation-id",
  "x-process-time",
  "x-ratelimit-limit",
  "x-ratelimit-remaining",
  "x-ratelimit-reset",
  "retry-after",
];

const DEFAULT_PROXY_TIMEOUT_MS = 120_000;
const LONG_RUNNING_PROXY_TIMEOUT_MS = 620_000;

function isLongRunningPath(pathSegments: string[]): boolean {
  const joined = pathSegments.join("/");
  return (
    joined.startsWith("v1/jd-generation/generate") ||
    joined.startsWith("v1/jd-generation/save") ||
    joined.startsWith("v1/resume-parsing/upload") ||
    joined.startsWith("v1/candidates/upload") ||
    joined.startsWith("v1/job-matching/match") ||
    joined.startsWith("v1/job-matching/rank")
  );
}

function isLongRunningStreamPath(pathSegments: string[]): boolean {
  return pathSegments.join("/").startsWith("v1/job-matching/match-stream");
}

function proxyTimeoutMs(pathSegments: string[]): number {
  if (isLongRunningPath(pathSegments) || isLongRunningStreamPath(pathSegments)) {
    return LONG_RUNNING_PROXY_TIMEOUT_MS;
  }
  return DEFAULT_PROXY_TIMEOUT_MS;
}

function longRunningTimeoutMessage(pathSegments: string[]): string {
  const joined = pathSegments.join("/");
  if (
    joined.includes("resume-parsing/upload") ||
    joined.includes("candidates/upload")
  ) {
    return (
      "Request timed out while parsing the resume. Document Intelligence and AI " +
      "extraction can take several minutes — retry or check API logs."
    );
  }
  if (joined.includes("job-matching/match")) {
    return (
      "Request timed out while running HSS-D job matching. The specialist swarm can " +
      "take several minutes — retry or check API logs."
    );
  }
  return (
    "Request timed out while waiting for the backend. JD generation can take " +
    "several minutes — retry or check API logs."
  );
}

function isStreamingContentType(contentType: string | null): boolean {
  if (!contentType) {
    return false;
  }
  const lower = contentType.toLowerCase();
  return (
    lower.includes("text/event-stream") ||
    lower.includes("application/x-ndjson") ||
    lower.includes("application/stream+json")
  );
}

function buildResponseHeaders(backendResponse: Response): Headers {
  const responseHeaders = new Headers();
  const setCookies =
    typeof backendResponse.headers.getSetCookie === "function"
      ? backendResponse.headers.getSetCookie()
      : [];
  for (const cookie of setCookies) {
    responseHeaders.append("set-cookie", cookie);
  }
  for (const name of FORWARD_RESPONSE_HEADERS) {
    if (name === "set-cookie") {
      continue;
    }
    const value = backendResponse.headers.get(name);
    if (value) {
      responseHeaders.set(name, value);
    }
  }
  if (!responseHeaders.has("content-type")) {
    const ct = backendResponse.headers.get("content-type");
    if (ct) {
      responseHeaders.set("content-type", ct);
    }
  }
  if (isStreamingContentType(backendResponse.headers.get("content-type"))) {
    responseHeaders.set("cache-control", "no-cache, no-transform");
    responseHeaders.set("connection", "keep-alive");
    responseHeaders.set("x-accel-buffering", "no");
  }
  return responseHeaders;
}

async function proxyToBackend(
  request: NextRequest,
  pathSegments: string[]
): Promise<NextResponse> {
  const incomingUrl = new URL(request.url);
  const targetPath = `/api/${pathSegments.join("/")}`;
  const targetUrl = `${backendBaseUrl()}${targetPath}${incomingUrl.search}`;

  const headers = new Headers();
  for (const name of FORWARD_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value) {
      headers.set(name, value);
    }
  }

  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    // Follow backend trailing-slash redirects (FastAPI 307). "manual" surfaced
    // "Temporary Redirect" to the browser when listing /api/v1/candidates.
    redirect: "follow",
  };

  if (request.method !== "GET" && request.method !== "HEAD") {
    if (request.body) {
      init.body = request.body;
      init.duplex = "half";
    }
  }

  try {
    const timeoutMs = proxyTimeoutMs(pathSegments);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    let backendResponse: Response;
    try {
      backendResponse = await fetch(targetUrl, {
        ...init,
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeoutId);
    }

    const responseHeaders = buildResponseHeaders(backendResponse);
    const contentType = backendResponse.headers.get("content-type");

    if (isStreamingContentType(contentType) && backendResponse.body) {
      return new NextResponse(backendResponse.body, {
        status: backendResponse.status,
        headers: responseHeaders,
      });
    }

    const body = await backendResponse.arrayBuffer();
    return new NextResponse(body, {
      status: backendResponse.status,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error("BFF proxy error:", targetUrl, error);
    const isAbort =
      error instanceof Error &&
      (error.name === "AbortError" || error.message.includes("aborted"));
    if (isAbort) {
      return NextResponse.json(
        {
          detail: longRunningTimeoutMessage(pathSegments),
          backend_url: backendBaseUrl(),
          path: targetPath,
        },
        { status: 504 }
      );
    }
    return NextResponse.json(
      {
        detail: "Backend unavailable",
        backend_url: backendBaseUrl(),
        path: targetPath,
      },
      { status: 502 }
    );
  }
}

type RouteContext = { params: { path: string[] } };

export async function GET(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path);
}

export async function POST(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path);
}

export async function PUT(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path);
}

export async function PATCH(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path);
}

export async function OPTIONS(request: NextRequest, context: RouteContext) {
  return proxyToBackend(request, context.params.path);
}
