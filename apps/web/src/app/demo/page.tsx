import Link from "next/link";
import { auth } from "@clerk/nextjs/server";
import {
  fetchRecommendations,
  type MatchBreakdown,
  type RecommendationsResponse,
} from "@/lib/api";

export const dynamic = "force-dynamic";

interface DemoSearchParams {
  source_user_id?: string;
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

  // Auth precedence matches the API: a Clerk JWT wins; otherwise we
  // fall back to the source_user_id query param (the synthetic-corpus
  // demo path). If neither is present, render the help block.
  // Keep `session` whole rather than destructuring so Clerk's `getToken`
  // keeps its `this` binding.
  const session = await auth();
  const bearerToken = session.userId ? await session.getToken() : null;
  const sourceUserId = params.source_user_id;

  if (!bearerToken && !sourceUserId) {
    return <EmptyState />;
  }

  let payload: RecommendationsResponse | undefined;
  let error: string | null = null;
  try {
    payload = await fetchRecommendations({
      sourceUserId,
      radiusM,
      limit,
      bearerToken: bearerToken ?? undefined,
    });
  } catch (e) {
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
            <code className="text-xs">
              {bearerToken ? "JWT-derived" : sourceUserId}
            </code>
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
      <h1 className="text-2xl font-semibold tracking-tight">Recommendations demo</h1>
      <p className="mt-2 text-sm opacity-70">
        Two ways to drive this page:
      </p>

      <ol className="mt-4 list-decimal space-y-3 pl-5 text-sm">
        <li>
          <strong>Sign in</strong> (top right). With a Clerk JWT in scope the
          API derives the source user from the token automatically. You will
          still need a profile row — that flow lands next.
        </li>
        <li>
          <strong>Pass a seed user id</strong> in the URL. From the Codespace
          terminal:
          <pre className="mt-2 overflow-x-auto rounded bg-black/5 p-2 font-mono text-xs dark:bg-white/10">
{`docker compose -f infra/compose/docker-compose.yml exec db \\
  psql -U hangpost -d hangpost -tA -c \\
  "SELECT id FROM users WHERE auth_provider='seed' LIMIT 1;"`}
          </pre>
          Then visit{" "}
          <code className="rounded bg-black/5 px-1 py-0.5 text-xs dark:bg-white/10">
            /demo?source_user_id=&lt;uuid&gt;
          </code>
          .
        </li>
      </ol>
    </main>
  );
}
