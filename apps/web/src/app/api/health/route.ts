import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

function backendBaseUrl(): string {
  const env = process.env as Record<string, string | undefined>;
  const raw =
    env["BFF_BACKEND_URL"] ||
    env["BACKEND_INTERNAL_URL"] ||
    "http://localhost:8000";
  return raw.replace(/\/+$/, "");
}

/** Explicit health proxy (used by UI connection checks). */
export async function GET() {
  const targetUrl = `${backendBaseUrl()}/api/health`;
  try {
    const backendResponse = await fetch(targetUrl, { cache: "no-store" });
    const body = await backendResponse.text();
    return new NextResponse(body, {
      status: backendResponse.status,
      headers: {
        "content-type":
          backendResponse.headers.get("content-type") || "application/json",
      },
    });
  } catch (error) {
    console.error("BFF health proxy error:", targetUrl, error);
    return NextResponse.json(
      {
        detail: "Backend unavailable",
        backend_url: backendBaseUrl(),
        path: "/api/health",
        error: error instanceof Error ? error.message : String(error),
      },
      { status: 502 }
    );
  }
}
