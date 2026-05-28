/**
 * Minimal API client. In Phase 1 this is replaced by a typed client
 * generated from the FastAPI OpenAPI schema (packages/shared-types).
 */

// Server-side renders run inside the web container, where "localhost" is the
// web container itself — not the API. Use the internal service URL there and
// the public (browser-reachable) URL in the client.
const BROWSER_API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_URL =
  typeof window === "undefined"
    ? process.env.API_INTERNAL_URL ?? BROWSER_API_URL
    : BROWSER_API_URL;

export interface ApiHealth {
  ok: boolean;
  version: string | null;
}

export async function checkApiHealth(): Promise<ApiHealth> {
  try {
    const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
    if (!res.ok) return { ok: false, version: null };
    const data = (await res.json()) as { status: string; version: string };
    return { ok: data.status === "ok", version: data.version };
  } catch {
    return { ok: false, version: null };
  }
}
