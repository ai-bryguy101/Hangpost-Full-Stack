"use client";

import { useEffect, useRef, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import {
  postOutcome,
  type MatchBreakdown,
  type OutcomeAction,
  type RecommendationResult,
} from "@/lib/api";

// Fields that contribute to MatchBreakdown.total_score. A chip is "lit"
// when its component is > 0 — a visual proxy for "this signal fired".
const COMPONENT_FIELDS: Array<{ key: keyof MatchBreakdown; label: string }> = [
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

export default function RecommendationList({
  results,
}: {
  results: RecommendationResult[];
}) {
  const { getToken } = useAuth();
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [requested, setRequested] = useState<Set<string>>(new Set());
  const viewedFired = useRef(false);

  // Fire `viewed` once per surfaced impression on mount (fire-and-forget —
  // outcome capture must never block or break the demo render). The ref
  // guards against React's double-invoke in dev and any re-render.
  useEffect(() => {
    if (viewedFired.current) return;
    viewedFired.current = true;
    void (async () => {
      const token = await getToken();
      if (!token) return;
      for (const r of results) {
        void postOutcome(r.impression_id, "viewed", token).catch(() => {});
      }
    })();
  }, [results, getToken]);

  async function record(impressionId: string, action: OutcomeAction) {
    const token = await getToken();
    if (!token) return;
    void postOutcome(impressionId, action, token).catch(() => {});
  }

  function dismiss(impressionId: string) {
    setDismissed((prev) => {
      const next = new Set(prev);
      next.add(impressionId);
      return next;
    });
  }

  const visible = results.filter((r) => !dismissed.has(r.impression_id));

  if (visible.length === 0) {
    return (
      <p className="rounded-lg border border-black/10 p-6 text-sm opacity-70 dark:border-white/15">
        No more picks to show.
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-3">
      {visible.map((r) => {
        const requestSent = requested.has(r.impression_id);
        return (
          <li
            key={r.impression_id}
            className="rounded-lg border border-black/10 p-4 dark:border-white/15"
          >
            <div className="flex items-baseline justify-between gap-3">
              <button
                type="button"
                onClick={() => void record(r.impression_id, "profile_opened")}
                className="text-left"
                title="Open profile (records profile_opened)"
              >
                <div className="text-sm opacity-50">#{r.rank_position}</div>
                <h2 className="text-lg font-medium hover:underline">
                  {r.display_name}
                </h2>
                <p className="text-sm opacity-60">@{r.handle}</p>
              </button>
              <div className="text-right">
                <div className="font-mono text-lg">{r.score.toFixed(3)}</div>
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

            <div className="mt-3 flex gap-2 text-xs">
              <button
                type="button"
                disabled={requestSent}
                onClick={() => {
                  setRequested((prev) => new Set(prev).add(r.impression_id));
                  void record(r.impression_id, "friend_request_sent");
                }}
                className="rounded border border-emerald-500/50 px-2 py-1 hover:bg-emerald-500/10 disabled:opacity-50"
              >
                {requestSent ? "Request sent ✓" : "Add friend"}
              </button>
              <button
                type="button"
                onClick={() => dismiss(r.impression_id)}
                className="rounded border border-black/15 px-2 py-1 opacity-70 hover:opacity-100 dark:border-white/20"
                title="Hide this pick"
              >
                Dismiss
              </button>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
