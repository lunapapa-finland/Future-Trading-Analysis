import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 px-6 py-10">
      <header className="flex flex-col gap-2">
        <p className="text-sm uppercase tracking-[0.2em] text-accent">Future Trading Analysis</p>
        <h1 className="text-3xl font-semibold text-white">Modern UI Migration</h1>
        <p className="text-slate-300">
          Next.js frontend consuming the existing Python analytics APIs. Choose a workspace to begin.
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          href="/trading"
          className="rounded-xl border border-accent/40 bg-surface/60 p-6 shadow-lg transition hover:-translate-y-1 hover:border-accent hover:shadow-accent/30"
        >
          <p className="text-lg font-semibold text-white">Trading Workspace</p>
          <p className="text-sm text-slate-300">Candles, multi-timeframe view, quick stats.</p>
        </Link>
        <Link
          href="/analysis"
          className="rounded-xl border border-accentMuted/40 bg-surface/60 p-6 shadow-lg transition hover:-translate-y-1 hover:border-highlight hover:shadow-highlight/30"
        >
          <p className="text-lg font-semibold text-white">Analysis Workspace</p>
          <p className="text-sm text-slate-300">Rolling metrics, envelopes, distributions.</p>
        </Link>
      </div>
    </main>
  );
}
