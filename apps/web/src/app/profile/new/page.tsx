"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { SignUpButton, useAuth, useUser } from "@clerk/nextjs";
import {
  ApiError,
  createProfile,
  postUserLocation,
  type ProfileInput,
} from "@/lib/api";

type LocationStatus = "idle" | "locating" | "set" | "error";

// Mirror the server's `_dedupe_lower`: drop blanks, dedupe case-insensitively,
// preserve first-seen order. Comma-separated input is intentionally minimal —
// the real chip picker lands with the Phase 2 designs (DECISIONS_LOG).
function splitList(raw: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split(",")) {
    const cleaned = part.trim();
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(cleaned);
  }
  return out;
}

export default function ProfileNewPage() {
  const router = useRouter();
  const { isLoaded, isSignedIn } = useUser();
  const { getToken } = useAuth();

  const [displayName, setDisplayName] = useState("");
  const [handle, setHandle] = useState("");
  const [age, setAge] = useState("");
  const [hometown, setHometown] = useState("");
  const [college, setCollege] = useState("");
  const [interests, setInterests] = useState("");
  const [likedTopics, setLikedTopics] = useState("");

  const [locationStatus, setLocationStatus] = useState<LocationStatus>("idle");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isLoaded) {
    return (
      <main className="mx-auto max-w-md px-6 py-12 text-sm opacity-60">Loading…</main>
    );
  }

  if (!isSignedIn) {
    return (
      <main className="mx-auto max-w-md px-6 py-12">
        <h1 className="text-2xl font-semibold tracking-tight">Set up your profile</h1>
        <p className="mt-2 text-sm opacity-70">
          You need to be signed in to create a profile.
        </p>
        <div className="mt-4">
          <SignUpButton mode="modal" signUpForceRedirectUrl="/profile/new">
            <button className="rounded bg-foreground px-3 py-1 text-sm text-background">
              Sign up
            </button>
          </SignUpButton>
        </div>
      </main>
    );
  }

  async function captureLocation() {
    setError(null);
    if (!("geolocation" in navigator)) {
      setError("Geolocation isn't available in this browser.");
      setLocationStatus("error");
      return;
    }
    setLocationStatus("locating");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const token = await getToken();
          if (!token) throw new Error("Sign-in expired; sign in again.");
          await postUserLocation(
            {
              latitude: pos.coords.latitude,
              longitude: pos.coords.longitude,
              accuracy_m: pos.coords.accuracy ? Math.round(pos.coords.accuracy) : null,
            },
            token,
          );
          setLocationStatus("set");
        } catch (e) {
          setError(e instanceof Error ? e.message : String(e));
          setLocationStatus("error");
        }
      },
      (geoErr) => {
        setError(`Couldn't get your location: ${geoErr.message}`);
        setLocationStatus("error");
      },
    );
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const token = await getToken();
      if (!token) throw new Error("Sign-in expired; sign in again.");
      const input: ProfileInput = {
        display_name: displayName.trim(),
        handle: handle.trim(),
        age: age ? Number(age) : null,
        hometown: hometown.trim() || null,
        college: college.trim() || null,
        interests: splitList(interests),
        liked_topics: splitList(likedTopics),
      };
      await createProfile(input, token);
      router.push("/demo");
    } catch (e) {
      // A profile already exists for this user — nothing to create, so
      // just send them to their picks instead of surfacing an error.
      if (e instanceof ApiError && e.status === 409) {
        router.push("/demo");
        return;
      }
      setError(e instanceof Error ? e.message : String(e));
      setSubmitting(false);
    }
  }

  const locationSet = locationStatus === "set";

  return (
    <main className="mx-auto max-w-md px-6 py-8">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Set up your profile</h1>
        <p className="mt-1 text-sm opacity-70">
          A few fields and your location, then we&apos;ll rank you against people
          nearby.
        </p>
      </header>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <Field label="Display name" hint="1–50 characters">
          <input
            required
            maxLength={50}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Handle" hint="3–30 chars: letters, digits, underscore">
          <input
            required
            pattern="[A-Za-z0-9_]{3,30}"
            title="3–30 characters: letters, digits, underscore"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Age" hint="18–120 (optional)">
          <input
            type="number"
            min={18}
            max={120}
            value={age}
            onChange={(e) => setAge(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Hometown" hint="optional">
          <input
            maxLength={120}
            value={hometown}
            onChange={(e) => setHometown(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="College" hint="optional">
          <input
            maxLength={160}
            value={college}
            onChange={(e) => setCollege(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Interests" hint="comma-separated, e.g. climbing, jazz, ramen">
          <input
            value={interests}
            onChange={(e) => setInterests(e.target.value)}
            className={inputClass}
          />
        </Field>

        <Field label="Liked topics" hint="comma-separated, e.g. startups, cycling">
          <input
            value={likedTopics}
            onChange={(e) => setLikedTopics(e.target.value)}
            className={inputClass}
          />
        </Field>

        <div className="rounded-lg border border-black/10 p-4 dark:border-white/15">
          <button
            type="button"
            onClick={captureLocation}
            disabled={locationStatus === "locating"}
            className="rounded border border-black/15 px-3 py-1.5 text-sm hover:bg-black/5 disabled:opacity-50 dark:border-white/20 dark:hover:bg-white/10"
          >
            {locationStatus === "locating" ? "Locating…" : "Use my current location"}
          </button>
          <p className="mt-2 text-xs opacity-60">
            {locationStatus === "set"
              ? "✓ Location saved."
              : "Required — the radius pre-filter needs to know where you are."}
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-red-500/50 bg-red-500/5 p-3 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={!locationSet || submitting}
          className="rounded bg-foreground px-4 py-2 text-sm text-background disabled:opacity-50"
          title={locationSet ? undefined : "Set your location first"}
        >
          {submitting ? "Creating…" : "Create profile & see my picks"}
        </button>
      </form>

      <p className="mt-8 text-xs opacity-50">
        <Link href="/" className="underline">
          ← back
        </Link>
      </p>
    </main>
  );
}

const inputClass =
  "w-full rounded border border-black/15 bg-transparent px-3 py-1.5 text-sm outline-none focus:border-black/40 dark:border-white/20 dark:focus:border-white/50";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="text-xs opacity-50">{hint}</span>}
    </label>
  );
}
