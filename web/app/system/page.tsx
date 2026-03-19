"use client";

import Link from "next/link";
import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";

export default function SystemPage() {
  return (
    <AppShell active="/system">
      <Card title="System Config">
        <p className="mb-4 text-sm text-slate-300">Portfolio and runtime configuration controls are grouped here.</p>
        <div className="grid gap-3 md:grid-cols-2">
          <Link href="/portfolio" className="rounded-xl border border-white/10 bg-white/5 p-4 transition hover:border-accent/40 hover:bg-accent/10">
            <p className="text-sm font-semibold text-white">Portfolio</p>
            <p className="mt-1 text-xs text-slate-300">Net-liq series, cashflow adjustments, and portfolio metrics.</p>
          </Link>
          <Link href="/config" className="rounded-xl border border-white/10 bg-white/5 p-4 transition hover:border-accent/40 hover:bg-accent/10">
            <p className="text-sm font-semibold text-white">Runtime Config</p>
            <p className="mt-1 text-xs text-slate-300">Data sources, manifest, paths, and system configuration.</p>
          </Link>
        </div>
      </Card>
    </AppShell>
  );
}
