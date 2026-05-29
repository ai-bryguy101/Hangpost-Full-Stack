import Link from "next/link";
import { auth } from "@clerk/nextjs/server";
import {
  ApiError,
  fetchRecommendations,
  type MatchBreakdown,
  type RecommendationsResponse,
} from "@/lib/api";

export const dynamic = "force-dynamic";

interface DemoSearchParams {
  radius_m?: string;
  limit?: string;
}

// Fields that contribute to MatchBreakdown.total_score. The rendered chip
// is "lit" when its component is > 0 — a visual proxy for "this signal
// actually fired for this pair".
const COMPONENT_FIELDS: Array<{
  key: keyof MatchBreakdown;
  label: string;
}> = [
  { key: "semantic_similarity", label: "semantic" },
  { key: "hometown_match", label: "hometown" },
  { key: "college_match", label: "college" },
  { key: "age_compatibility", label: "age" },
  { key: "interest_overlap", label: "interests" },
  { key: "liked_topic_overlap", label: "likes" },
  { key: "mutual_friends", label: "mutuals" },
];

function tierLabel(b: MatchBreakdown): string {
  if (b.has_mutual_friends && b.has_both_shared_background)
    return "Tier 1 · mutual + hometown + college";
  if (b.has_mutual_friends && b.has_shared_background)
    return "Tier 2 · mutual + shared background";
  if (b.has_mutual_friends) return "Tier 3 · mutual friend";
  if (b.has_both_shared_background) return "Tier 4 · hometown + college";
  if (b.has_shared_background) return "Tier 5 · hometown or college";
  return "Tier 6 · compatibility only";
}

export default async function DemoPage({
  searchParams,
}: {
  searchParams: Promise<DemoSearchParams>;
}) {
  const params = await searchParams;
  const radiusM = params.radius_m ? Number(params.radius_m) : 5000;
  const limit = params.limit ? Number(params.limit) : 10;

  // Clerk-auth-only: the API derives the source user from the JWT.
  // Keep `session` whole rather than destructuring so Clerk's `getToken`
  // keeps its `this` binding.
  const session = await auth();
  const bearerToken = session.userId ? await session.getToken() : null;

  if (!bearerToken) {
    return <EmptyState />;
  }

  let payload: RecommendationsResponse | undefined;
  let error: string | null = null;
  try {
    payload = await fetchRecommendations({ radiusM, limit, bearerToken });
  } catch (e) {
    // A signed-in user with no profile (404) or no location (409) just
    // hasn't finished onboarding — guide them there instead of erroring.
    if (e instanceof ApiError && (e.status === 404 || e.status === 409)) {
      return <OnboardingPrompt status={e.status} />;
    }
    error = e instanceof Error ? e.message : String(e);
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Recommendations</h1>
        <p className="mt-1 text-sm opacity-70">
          ST_DWithin pre-filter → hangpost_matching → JSONB impression log.
        </p>
      </header>

      <div className="mb-6 rounded-lg border border-black/10 p-4 text-sm dark:border-white/15">
        <div className="grid grid-cols-3 gap-2">
          <Metadata label="source">
            <code className="text-xs">JWT-derived</code>
          </Metadata>
          <Metadata label="radius_m">{radiusM}</Metadata>
          <Metadata label="model_version">
            {payload?.model_version ?? "—"}
          </Metadata>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/5 p-4 text-sm">
          <strong>API error.</strong> {error}
        </div>
      )}

      {payload && payload.results.length === 0 && (
        <div className="rounded-lg border border-black/10 p-6 text-sm opacity-70 dark:border-white/15">
          No candidates within {radiusM} m of the source. Try a larger radius
          (e.g. <code>?radius_m=20000</code>) or a different source user.
        </div>
      )}

      {payload && payload.results.length > 0 && (
        <ol className="flex flex-col gap-3">
          {payload.results.map((r) => (
            <li
              key={r.user_id}
              className="rounded-lg border border-black/10 p-4 dark:border-white/15"
            >
              <div className="flex items-baseline justify-between gap-3">
                <div>
                  <div className="text-sm opacity-50">#{r.rank_position}</div>
                  <h2 className="text-lg font-medium">{r.display_name}</h2>
                  <p className="text-sm opacity-60">@{r.handle}</p>
                </div>
                <div className="text-right">
                  <div className="font-mono text-lg">
                    {r.score.toFixed(3)}
                  </div>
                  <div className="text-xs opacity-50">total_score</div>
                </div>
              </div>

              <p className="mt-2 text-xs uppercase tracking-wide opacity-50">
                {tierLabel(r.breakdown)}
              </p>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {COMPONENT_FIELDS.map(({ key, label }) => {
                  const value = r.breakdown[key] as number;
                  const lit = value > 0;
                  return (
                    <span
                      key={key}
                      className={[
                        "rounded-full border px-2 py-0.5 font-mono text-[11px]",
                        lit
                          ? "border-emerald-500/50 bg-emerald-500/10"
                          : "border-black/10 opacity-40 dark:border-white/15",
                      ].join(" ")}
                      title={`${label}: ${value}`}
                    >
                      {label} {value.toFixed(2)}
                    </span>
                  );
                })}
              </div>
            </li>
          ))}
        </ol>
      )}

      <p className="mt-8 text-xs opacity-50">
        <Link href="/" className="underline">
          ← back
        </Link>
      </p>
    </main>
  );
}

function Metadata({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="text-xs uppercase tracking-wide opacity-50">{label}</div>
      <div>{children}</div>
    </div>
  );
}

function EmptyState() {
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">Your daily picks</h1>
      <p className="mt-2 text-sm opacity-70">
        Sign up and set up your profile to see yourself ranked against the
        people nearby.
      </p>
      <ol className="mt-4 list-decimal space-y-2 pl-5 text-sm">
        <li>
          <strong>Sign up</strong> (top right) — you&apos;ll be taken straight
          to profile setup.
        </li>
        <li>
          Fill in a few fields and tap <strong>Use my current location</strong>.
        </li>
        <li>You land back here with a ranked list and a full match breakdown.</li>
      </ol>
      <p className="mt-6 text-sm">
        Already signed in?{" "}
        <Link href="/profile/new" className="underline">
          Set up your profile →
        </Link>
      </p>
    </main>
  );
}

function OnboardingPrompt({ status }: { status: number }) {
  const needsLocation = status === 409;
  return (
    <main className="mx-auto max-w-2xl px-6 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">
        {needsLocation ? "Set your location" : "Finish your profile"}
      </h1>
      <p className="mt-2 text-sm opacity-70">
        {needsLocation
          ? "You're signed in, but we don't have a location for you yet — the radius pre-filter needs one before it can rank anybody."
          : "You're signed in, but you don't have a profile yet. Create one to get ranked."}
      </p>
      <p className="mt-6 text-sm">
        <Link href="/profile/new" className="underline">
          Go to profile setup →
        </Link>
      </p>
    </main>
  );
}
