/**
 * Minimal API client. In Phase 1 this is replaced by a typed client
 * generated from the FastAPI OpenAPI schema (packages/shared-types).
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
