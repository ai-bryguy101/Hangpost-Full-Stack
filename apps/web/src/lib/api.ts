/**
 * Minimal API client. In a later phase this is replaced by a typed
 * client generated from the FastAPI OpenAPI schema
 * (packages/shared-types).
 */

// Server-side renders run inside the web container, where "localhost" is
// the web container itself — not the API. Use the internal service URL
// there and the public (browser-reachable) URL in the client.
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

/** Verbatim shape of `MatchBreakdown` returned by `/recommendations`. */
export interface MatchBreakdown {
  total_score: number;
  has_mutual_friends: boolean;
  has_shared_background: boolean;
  has_both_shared_background: boolean;
  social_boost: number;
  interest_overlap: number;
  liked_topic_overlap: number;
  mutual_friends: number;
  hometown_match: number;
  college_match: number;
  age_compatibility: number;
  semantic_similarity: number;
}

export interface RecommendationResult {
  user_id: string;
  display_name: string;
  handle: string;
  rank_position: number;
  score: number;
  breakdown: MatchBreakdown;
}

export interface RecommendationsResponse {
  source_user_id: string;
  radius_m: number;
  model_version: string;
  results: RecommendationResult[];
}

export interface FetchRecommendationsOptions {
  sourceUserId?: string;
  radiusM?: number;
  limit?: number;
  /** Optional Clerk JWT — when set, the API derives the source from the token. */
  bearerToken?: string;
}

/** Either `sourceUserId` or `bearerToken` (or both) must be provided. */
export async function fetchRecommendations(
  opts: FetchRecommendationsOptions,
): Promise<RecommendationsResponse> {
  const params = new URLSearchParams();
  if (opts.sourceUserId) params.set("source_user_id", opts.sourceUserId);
  if (opts.radiusM !== undefined) params.set("radius_m", String(opts.radiusM));
  if (opts.limit !== undefined) params.set("limit", String(opts.limit));

  const headers: Record<string, string> = {};
  if (opts.bearerToken) headers.Authorization = `Bearer ${opts.bearerToken}`;

  const res = await fetch(`${API_URL}/recommendations?${params.toString()}`, {
    cache: "no-store",
    headers,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`recommendations ${res.status}: ${body || res.statusText}`);
  }
  return (await res.json()) as RecommendationsResponse;
}
