import Link from "next/link";
import { checkApiHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function Home() {
  const health = await checkApiHealth();

  return (
    <main className="mx-auto flex min-h-[80vh] max-w-md flex-col justify-center gap-6 p-8">
      <header>
        <h1 className="text-3xl font-bold">Hangpost</h1>
        <p className="mt-1 text-sm opacity-70">
          The city posterboard for people who just moved here.
        </p>
      </header>

      <section className="rounded-lg border border-black/10 p-4 dark:border-white/15">
        <h2 className="text-sm font-medium uppercase tracking-wide opacity-60">
          API status
        </h2>
        <p className="mt-1 font-mono text-sm">
          {health.ok ? `ok — v${health.version}` : "unreachable"}
        </p>
      </section>

      <section className="rounded-lg border border-black/10 p-4 dark:border-white/15">
        <h2 className="text-sm font-medium uppercase tracking-wide opacity-60">
          Demo
        </h2>
        <p className="mt-1 text-sm opacity-80">
          Live recommendations against the seeded DC corpus, with the engine&apos;s
          full <code>MatchBreakdown</code>.
        </p>
        <Link
          href="/demo"
          className="mt-3 inline-block rounded bg-foreground px-3 py-1.5 text-sm text-background"
        >
          Open the demo →
        </Link>
      </section>
    </main>
  );
}
