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

/** Thrown by {@link apiFetch} on a non-2xx response; carries the status
 * so callers can branch (e.g. a 409 "profile exists" → redirect). */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface ApiFetchOptions {
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  /** Clerk JWT; sent as a bearer token when present. */
  bearerToken?: string;
  query?: Record<string, string>;
}

/** Single fetch seam for the API: attaches the bearer token, serializes
 * JSON, and turns non-2xx responses into a typed {@link ApiError}. */
async function apiFetch<T>(path: string, opts: ApiFetchOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (opts.bearerToken) headers.Authorization = `Bearer ${opts.bearerToken}`;
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";

  const qs = opts.query ? `?${new URLSearchParams(opts.query).toString()}` : "";
  const res = await fetch(`${API_URL}${path}${qs}`, {
    method: opts.method ?? "GET",
    cache: "no-store",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new ApiError(res.status, detail || res.statusText);
  }
  return (await res.json()) as T;
}

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
  radiusM?: number;
  limit?: number;
  /** Clerk JWT. The API derives the source user from it — recommendations
   * are Clerk-auth-only, so this is required. */
  bearerToken: string;
}

export async function fetchRecommendations(
  opts: FetchRecommendationsOptions,
): Promise<RecommendationsResponse> {
  const query: Record<string, string> = {};
  if (opts.radiusM !== undefined) query.radius_m = String(opts.radiusM);
  if (opts.limit !== undefined) query.limit = String(opts.limit);
  return apiFetch<RecommendationsResponse>("/recommendations", {
    bearerToken: opts.bearerToken,
    query,
  });
}

/** Fields a user supplies to create their profile. Mirrors the API's
 * `ProfileCreate` schema; the server is the source of truth for
 * validation (handle regex, age 18-120, list dedupe). */
export interface ProfileInput {
  display_name: string;
  handle: string;
  age: number | null;
  hometown: string | null;
  college: string | null;
  interests: string[];
  liked_topics: string[];
}

export interface ProfileResponse {
  user_id: string;
  display_name: string;
  handle: string;
}

export async function createProfile(
  input: ProfileInput,
  bearerToken: string,
): Promise<ProfileResponse> {
  return apiFetch<ProfileResponse>("/profiles", {
    method: "POST",
    body: input,
    bearerToken,
  });
}

export interface LocationInput {
  latitude: number;
  longitude: number;
  accuracy_m: number | null;
}

export interface LocationResponse {
  latitude: number;
  longitude: number;
  accuracy_m: number | null;
  updated_at: string;
}

export async function postUserLocation(
  input: LocationInput,
  bearerToken: string,
): Promise<LocationResponse> {
  return apiFetch<LocationResponse>("/user-locations", {
    method: "POST",
    body: input,
    bearerToken,
  });
}
