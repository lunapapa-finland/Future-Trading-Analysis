"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import type { ConfigResponse, SymbolConfig } from "@/lib/config";
import { fetchConfig } from "@/lib/config";
import { getDataFetchStatus, postDataFetchRun } from "@/lib/api";

type FetchStatusRow = {
  symbol: string;
  data_path: string;
  exists: boolean;
  rows: number;
  last_date: string;
  status: string;
  error?: string;
};

export default function ConfigPage() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchRows, setFetchRows] = useState<FetchStatusRow[]>([]);
  const [fetchLoading, setFetchLoading] = useState(false);
  const [fetchBusy, setFetchBusy] = useState(false);
  const [fetchMessage, setFetchMessage] = useState("");

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

  async function loadFetchStatus() {
    setFetchLoading(true);
    try {
      const resp = await getDataFetchStatus();
      setFetchRows(resp.rows || []);
    } catch (err) {
      setFetchMessage((err as Error).message || "Failed to load fetch status");
    } finally {
      setFetchLoading(false);
    }
  }

  async function runManualFetch() {
    setFetchBusy(true);
    setFetchMessage("");
    try {
      const resp = await postDataFetchRun({ max_retries: 3, retry_delay: 10 });
      setFetchMessage(`Fetch done. summary=${JSON.stringify(resp.summary)}`);
      await loadFetchStatus();
    } catch (err) {
      setFetchMessage((err as Error).message || "Manual fetch failed");
    } finally {
      setFetchBusy(false);
    }
  }

  useEffect(() => {
    loadFetchStatus();
  }, []);

  return (
    <AppShell active="/config">
      <div className="space-y-4">
        <div className="flex flex-col gap-1">
          <p className="text-xs uppercase tracking-[0.2em] text-accent sm:text-sm">Configuration</p>
          <h1 className="text-xl font-semibold text-white sm:text-2xl">Symbol data paths</h1>
          <p className="text-sm text-slate-300">Read-only view of symbols and their CSV sources. Editing coming later.</p>
        </div>

        {loading && <p className="text-slate-300">Loading...</p>}
        {error && <p className="text-red-400">{error}</p>}

        {config ? (
          <>
            <DataFetchPanel
              rows={fetchRows}
              loading={fetchLoading}
              busy={fetchBusy}
              message={fetchMessage}
              onRefresh={loadFetchStatus}
              onRun={runManualFetch}
            />
            {config.runtime_manifest ? <RuntimeManifestPanel manifest={config.runtime_manifest} /> : null}
            <SymbolTable symbols={config.symbols} />
            {config.timeframes?.length ? <TimeframeList timeframes={config.timeframes} /> : null}
            <HoldTypeInfo />
          </>
        ) : null}
      </div>
    </AppShell>
  );
}

function DataFetchPanel({
  rows,
  loading,
  busy,
  message,
  onRefresh,
  onRun,
}: {
  rows: FetchStatusRow[];
  loading: boolean;
  busy: boolean;
  message: string;
  onRefresh: () => void;
  onRun: () => void;
}) {
  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-surface/60 p-4 shadow-lg">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm uppercase tracking-[0.2em] text-accent">Data Fetch</p>
          <p className="mt-1 text-slate-300">Per-symbol future data status and manual yfinance fetch trigger.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onRefresh} disabled={loading || busy} className="rounded border border-white/20 px-3 py-2 text-xs text-slate-200 disabled:opacity-60">
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <button onClick={onRun} disabled={busy} className="rounded border border-cyan-300/40 px-3 py-2 text-xs text-cyan-200 disabled:opacity-60">
            {busy ? "Fetching..." : "Fetch Now"}
          </button>
        </div>
      </div>
      {message ? <p className="text-xs text-slate-300">{message}</p> : null}
      <div className="overflow-x-auto">
        <table className="min-w-[860px] w-full text-sm text-white">
          <thead className="text-xs uppercase tracking-[0.12em] text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">Symbol</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-right">Rows</th>
              <th className="px-3 py-2 text-left">Last Date</th>
              <th className="px-3 py-2 text-left">Path</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {rows.map((r) => (
              <tr key={r.symbol}>
                <td className="px-3 py-2 font-semibold text-accent">{r.symbol}</td>
                <td className="px-3 py-2">
                  <span
                    className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${
                      r.status === "ready"
                        ? "border-emerald-400/50 text-emerald-300"
                        : r.status === "empty"
                          ? "border-amber-400/50 text-amber-300"
                          : r.status === "missing"
                            ? "border-slate-400/50 text-slate-300"
                            : "border-red-400/50 text-red-300"
                    }`}
                  >
                    {r.status}
                  </span>
                  {r.error ? <span className="ml-2 text-[11px] text-red-300">{r.error}</span> : null}
                </td>
                <td className="px-3 py-2 text-right">{r.rows}</td>
                <td className="px-3 py-2">{r.last_date || "empty"}</td>
                <td className="px-3 py-2 text-slate-300" title={r.data_path}>
                  <span className="block max-w-[360px] truncate">{r.data_path}</span>
                </td>
              </tr>
            ))}
            {!rows.length ? (
              <tr>
                <td className="px-3 py-3 text-slate-500" colSpan={5}>No symbol status rows.</td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function RuntimeManifestPanel({
  manifest,
}: {
  manifest: NonNullable<ConfigResponse["runtime_manifest"]>;
}) {
  const sourceEntries = Object.entries(manifest.sources || {});
  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-surface/60 p-4 shadow-lg">
      <div>
        <p className="text-sm uppercase tracking-[0.2em] text-accent">Runtime Manifest</p>
        <p className="mt-1 text-slate-300">Single control view for active data roots and CSV sources used by backend APIs.</p>
      </div>
      {manifest.app_config ? (
        <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
          <p className="text-[11px] uppercase tracking-[0.12em] text-slate-400">App Config File</p>
          <p className="truncate text-sm text-white" title={manifest.app_config.config_path}>
            {manifest.app_config.config_path}
          </p>
        </div>
      ) : null}
      <div className="grid gap-2 md:grid-cols-2">
        {Object.entries(manifest.roots || {}).map(([k, v]) => (
          <div key={k} className="rounded-lg border border-white/10 bg-white/5 px-3 py-2">
            <p className="text-[11px] uppercase tracking-[0.12em] text-slate-400">{k}</p>
            <p className="truncate text-sm text-white" title={v}>{v}</p>
          </div>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[920px] w-full text-sm text-white">
          <thead className="text-xs uppercase tracking-[0.12em] text-slate-400">
            <tr>
              <th className="px-3 py-2 text-left">Source</th>
              <th className="px-3 py-2 text-left">Path</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-right">Rows</th>
              <th className="px-3 py-2 text-left">Columns</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {sourceEntries.map(([name, info]) => {
              const ok = info.exists && info.readable;
              return (
                <tr key={name}>
                  <td className="px-3 py-2 font-semibold text-accent">{name}</td>
                  <td className="px-3 py-2 text-slate-100" title={info.path}>
                    <span className="block max-w-[320px] truncate">{info.path}</span>
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-flex rounded-full border px-2 py-0.5 text-xs ${
                        ok ? "border-emerald-400/50 text-emerald-300" : "border-red-400/50 text-red-300"
                      }`}
                    >
                      {ok ? "ready" : info.exists ? "unreadable" : "missing"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">{info.rows}</td>
                  <td className="px-3 py-2 text-slate-300">
                    <span className="block max-w-[300px] truncate" title={(info.columns || []).join(", ")}>
                      {(info.columns || []).join(", ") || "-"}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SymbolTable({ symbols }: { symbols: SymbolConfig[] }) {
  return (
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-surface/60 shadow-lg">
      <div className="border-b border-white/5 bg-white/5 px-4 py-3 text-xs uppercase tracking-[0.15em] text-slate-400">
        Symbols
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-[720px] w-full text-sm text-white">
          <thead className="text-xs uppercase tracking-[0.15em] text-slate-400">
            <tr>
              <th className="px-4 py-3 text-left">Symbol</th>
              <th className="px-4 py-3 text-left">Asset Class</th>
              <th className="px-4 py-3 text-left">Data Path</th>
              <th className="px-4 py-3 text-left">Performance Path</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {symbols.map((s) => (
              <tr key={s.symbol}>
                <td className="px-4 py-3 font-semibold text-accent">{s.symbol}</td>
                <td className="px-4 py-3 text-slate-200">{s.asset_class}</td>
                <td className="px-4 py-3 text-slate-100" title={s.data_path}>
                  <span className="block max-w-[260px] truncate">{s.data_path}</span>
                </td>
                <td className="px-4 py-3 text-slate-100" title={s.performance_path}>
                  <span className="block max-w-[260px] truncate">{s.performance_path}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
