"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import type { ConfigResponse, SymbolConfig } from "@/lib/config";
import { fetchConfig } from "@/lib/config";

export default function ConfigPage() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    fetchConfig()
      .then((data) => {
        if (mounted) {
          setConfig(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setError(err.message || "Failed to load config");
          setLoading(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <AppShell active="/config">
      <div className="space-y-4">
        <div className="flex flex-col gap-1">
          <p className="text-sm uppercase tracking-[0.2em] text-accent">Configuration</p>
          <h1 className="text-2xl font-semibold text-white">Symbol data paths</h1>
          <p className="text-slate-300">Read-only view of symbols and their CSV sources. Editing coming later.</p>
        </div>

        {loading && <p className="text-slate-300">Loading...</p>}
        {error && <p className="text-red-400">{error}</p>}

        {config ? (
          <>
            <SymbolTable symbols={config.symbols} />
            {config.timeframes?.length ? <TimeframeList timeframes={config.timeframes} /> : null}
            <HoldTypeInfo />
          </>
        ) : null}
      </div>
    </AppShell>
  );
}

function SymbolTable({ symbols }: { symbols: SymbolConfig[] }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-surface/60 shadow-lg">
      <div className="grid grid-cols-4 gap-4 border-b border-white/5 bg-white/5 px-4 py-3 text-xs uppercase tracking-[0.15em] text-slate-400">
        <span>Symbol</span>
        <span>Asset Class</span>
        <span>Data Path</span>
        <span>Performance Path</span>
      </div>
      <div className="divide-y divide-white/5">
        {symbols.map((s) => (
          <div key={s.symbol} className="grid grid-cols-4 gap-4 px-4 py-3 text-sm text-white">
            <span className="font-semibold text-accent">{s.symbol}</span>
            <span className="text-slate-200">{s.asset_class}</span>
            <span className="truncate text-slate-100" title={s.data_path}>
              {s.data_path}
            </span>
            <span className="truncate text-slate-100" title={s.performance_path}>
              {s.performance_path}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function HoldTypeInfo() {
  const rows = [
    { label: "Scalp", window: "<= 5 minutes" },
    { label: "Scalp/Swing", window: "5-30 minutes" },
    { label: "Swing", window: ">= 30 minutes" },
  ];

  return (
    <div className="rounded-2xl border border-white/10 bg-surface/60 p-4 shadow-lg">
      <p className="text-sm uppercase tracking-[0.2em] text-accent">Trade Type Buckets</p>
      <p className="mt-1 text-slate-300">Display-only mapping used by the trading view.</p>
      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
        {rows.map((row) => (
          <div key={row.label} className="rounded-xl border border-white/5 bg-white/5 px-3 py-2">
            <div className="text-sm font-semibold text-white">{row.label}</div>
            <div className="text-xs text-slate-300">{row.window}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TimeframeList({ timeframes }: { timeframes: string[] }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-surface/60 p-4 shadow-lg">
      <p className="text-sm uppercase tracking-[0.2em] text-accent">Timeframes</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {timeframes.map((tf) => (
          <span
            key={tf}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-sm text-white"
          >
            {tf}
          </span>
        ))}
      </div>
    </div>
  );
}
