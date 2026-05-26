import { checkApiHealth } from "@/lib/api";

export default async function Home() {
  const health = await checkApiHealth();

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-6 p-8">
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
    </main>
  );
}
