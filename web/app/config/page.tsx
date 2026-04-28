"use client";

import { ReactNode, useEffect, useState } from "react";
import { AppShell } from "@/components/layout/app-shell";
import type { ConfigResponse, RuntimeConfigField, RuntimeConfigResponse, SymbolConfig } from "@/lib/config";
import { fetchConfig, fetchRuntimeConfig, patchRuntimeConfig } from "@/lib/config";
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

type RateLimitStatus = {
  active: boolean;
  cooldown_until: string;
  remaining_seconds: number;
};

function formatDateTime(iso: string, timeZone?: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-GB", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone,
    timeZoneName: "short",
  }).format(d);
}

function describeRateLimit(rateLimit?: RateLimitStatus): string {
  if (!rateLimit?.active) return "";
  const localAt = formatDateTime(rateLimit.cooldown_until);
  const chicagoAt = formatDateTime(rateLimit.cooldown_until, "America/Chicago");
  const sec = Math.max(0, Number(rateLimit.remaining_seconds || 0));
  const min = Math.ceil(sec / 60);
  return `Rate-limited by yfinance. Next retry in ~${min} min (${sec}s). Available at ${localAt} (local) / ${chicagoAt} (Chicago).`;
}

function summarizeFetchResult(summary: {
  symbols?: number;
  days_attempted?: number;
  saved?: number;
  skipped?: number;
  failed?: number;
  rate_limited?: boolean;
  cooldown_until?: string;
}): string {
  if (summary.rate_limited) {
    if ((summary.days_attempted ?? 0) === 0) {
      const nextLocal = summary.cooldown_until ? formatDateTime(summary.cooldown_until) : "";
      const nextChicago = summary.cooldown_until ? formatDateTime(summary.cooldown_until, "America/Chicago") : "";
      return `Fetch blocked by an active yfinance cooldown from an earlier run. No request was attempted now. Next try: ${nextLocal} (local) / ${nextChicago} (Chicago).`;
    }
    const nextLocal = summary.cooldown_until ? formatDateTime(summary.cooldown_until) : "";
    const nextChicago = summary.cooldown_until ? formatDateTime(summary.cooldown_until, "America/Chicago") : "";
    return `Fetch hit yfinance rate limit during this run. Next try: ${nextLocal} (local) / ${nextChicago} (Chicago).`;
  }
  return `Fetch done. saved=${summary.saved ?? 0}, skipped=${summary.skipped ?? 0}, failed=${summary.failed ?? 0}, days_attempted=${summary.days_attempted ?? 0}, symbols=${summary.symbols ?? 0}.`;
}

export default function ConfigPage() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fetchRows, setFetchRows] = useState<FetchStatusRow[]>([]);
  const [fetchLoading, setFetchLoading] = useState(false);
  const [fetchBusy, setFetchBusy] = useState(false);
  const [fetchMessage, setFetchMessage] = useState("");
  const [fetchRateLimit, setFetchRateLimit] = useState<RateLimitStatus | undefined>(undefined);
  const [runtimeConfig, setRuntimeConfig] = useState<RuntimeConfigResponse | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(true);
  const [runtimeSaving, setRuntimeSaving] = useState(false);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [runtimeMessage, setRuntimeMessage] = useState("");
  const [runtimeDraft, setRuntimeDraft] = useState<Record<string, unknown>>({});

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

  async function loadRuntimeConfig() {
    setRuntimeLoading(true);
    setRuntimeError(null);
    try {
      const data = await fetchRuntimeConfig();
      setRuntimeConfig(data);
      setRuntimeDraft(draftFromFields(data.fields));
    } catch (err) {
      setRuntimeError((err as Error).message || "Failed to load runtime config");
    } finally {
      setRuntimeLoading(false);
    }
  }

  useEffect(() => {
    loadRuntimeConfig();
  }, []);

  async function loadFetchStatus() {
    setFetchLoading(true);
    try {
      const resp = await getDataFetchStatus();
      setFetchRows(resp.rows || []);
      setFetchRateLimit(resp.rate_limit);
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
      const resp = await postDataFetchRun();
      setFetchMessage(summarizeFetchResult(resp.summary || {}));
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
          <h1 className="text-xl font-semibold text-white sm:text-2xl">Runtime Config</h1>
        </div>

        {loading && <p className="text-slate-300">Loading...</p>}
        {error && <p className="text-red-400">{error}</p>}

        {config ? (
          <>
            <ConfigDisclosure title="Data Fetch" badge="fetch enabled">
              <DataFetchPanel
                rows={fetchRows}
                loading={fetchLoading}
                busy={fetchBusy}
                message={fetchMessage}
                rateLimit={fetchRateLimit}
                onRefresh={loadFetchStatus}
                onRun={runManualFetch}
              />
            </ConfigDisclosure>
            <ConfigDisclosure title="Live Runtime Settings" badge="live">
              <RuntimeConfigEditor
                runtimeConfig={runtimeConfig}
                draft={runtimeDraft}
                loading={runtimeLoading}
                saving={runtimeSaving}
                error={runtimeError}
                message={runtimeMessage}
                onChange={(key, value) => {
                  setRuntimeDraft((current) => ({ ...current, [key]: value }));
                  setRuntimeMessage("");
                }}
                onRefresh={loadRuntimeConfig}
                onSave={async () => {
                  if (!runtimeConfig) return;
                  setRuntimeSaving(true);
                  setRuntimeError(null);
                  setRuntimeMessage("");
                  try {
                    const saved = await patchRuntimeConfig(runtimeDraft);
                    setRuntimeConfig(saved);
                    setRuntimeDraft(draftFromFields(saved.fields));
                    setRuntimeMessage("Saved. Changes apply to the next backend operation.");
                    const refreshed = await fetchConfig();
                    setConfig(refreshed);
                  } catch (err) {
                    setRuntimeError((err as Error).message || "Failed to save runtime config");
                  } finally {
                    setRuntimeSaving(false);
                  }
                }}
              />
            </ConfigDisclosure>
            <ConfigDisclosure title="Static Manifest" badge="rebuild required">
              {config.runtime_manifest ? <RuntimeManifestPanel manifest={config.runtime_manifest} /> : null}
              <SymbolTable symbols={config.symbols} />
              <HoldTypeInfo />
            </ConfigDisclosure>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}

function ConfigDisclosure({
  title,
  badge,
  children,
}: {
  title: string;
  badge: string;
  children: ReactNode;
}) {
  return (
    <details className="group rounded-2xl border border-white/10 bg-surface/60 shadow-lg">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-4">
        <div className="flex min-w-0 items-center gap-3">
          <span className="text-sm text-slate-400 transition group-open:rotate-90">›</span>
          <h2 className="truncate text-base font-semibold text-white">{title}</h2>
        </div>
        <span className="shrink-0 rounded border border-white/10 px-2 py-1 text-[11px] uppercase tracking-[0.12em] text-slate-300">{badge}</span>
      </summary>
      <div className="border-t border-white/10 p-4">{children}</div>
    </details>
  );
}

function formatDraftValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.join(", ");
  return value;
}

function draftFromFields(fields: RuntimeConfigField[]): Record<string, unknown> {
  return Object.fromEntries(fields.map((field) => [field.key, formatDraftValue(field.value)]));
}

function fieldsBySection(fields: RuntimeConfigField[]): Array<[string, RuntimeConfigField[]]> {
  const grouped = new Map<string, RuntimeConfigField[]>();
  fields.forEach((field) => {
    grouped.set(field.section, [...(grouped.get(field.section) || []), field]);
  });
  return Array.from(grouped.entries());
}

function RuntimeConfigEditor({
  runtimeConfig,
  draft,
  loading,
  saving,
  error,
  message,
  onChange,
  onRefresh,
  onSave,
}: {
  runtimeConfig: RuntimeConfigResponse | null;
  draft: Record<string, unknown>;
  loading: boolean;
  saving: boolean;
  error: string | null;
  message: string;
  onChange: (key: string, value: unknown) => void;
  onRefresh: () => void;
  onSave: () => void;
}) {
  const sections = fieldsBySection(runtimeConfig?.fields || []);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {runtimeConfig?.config_path ? (
            <p className="max-w-full truncate text-xs text-slate-400" title={runtimeConfig.config_path}>
              {runtimeConfig.config_path}
            </p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <button onClick={onRefresh} disabled={loading || saving} className="rounded border border-white/20 px-3 py-2 text-xs text-slate-200 disabled:opacity-60">
            {loading ? "Refreshing..." : "Refresh"}
          </button>
          <button onClick={onSave} disabled={loading || saving || !runtimeConfig} className="rounded border border-cyan-300/40 px-3 py-2 text-xs text-cyan-200 disabled:opacity-60">
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>
      {error ? <p className="rounded border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">{error}</p> : null}
      {message ? <p className="rounded border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">{message}</p> : null}
      {loading ? <p className="text-sm text-slate-300">Loading live settings...</p> : null}
      {!loading && !sections.length ? <p className="text-sm text-slate-300">No live-editable settings returned by backend.</p> : null}
      <div className="grid gap-4 xl:grid-cols-2">
        {sections.map(([section, fields]) => (
          <div key={section} className="rounded-xl border border-white/10 bg-white/5 p-3">
            <h2 className="text-sm font-semibold text-white">{section}</h2>
            <div className="mt-3 space-y-3">
              {fields.map((field) => (
                <RuntimeFieldControl
                  key={field.key}
                  field={field}
                  value={draft[field.key]}
                  onChange={(value) => onChange(field.key, value)}
                />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RuntimeFieldControl({
  field,
  value,
  onChange,
}: {
  field: RuntimeConfigField;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const common = "mt-1 w-full rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-sm text-white outline-none focus:border-accent";
  return (
    <label className="block">
      <div className="flex items-start justify-between gap-3">
        <span className="text-sm font-medium text-slate-100">{field.label}</span>
        <span className="shrink-0 rounded border border-white/10 px-2 py-0.5 text-[11px] text-slate-400">live</span>
      </div>
      <p className="mt-0.5 text-xs text-slate-400">{field.description}</p>
      {field.type === "boolean" ? (
        <select className={common} value={String(Boolean(value))} onChange={(e) => onChange(e.target.value === "true")}>
          <option value="true">Enabled</option>
          <option value="false">Disabled</option>
        </select>
      ) : (
        <input
          className={common}
          type={field.type === "number" || field.type === "integer" ? "number" : field.type === "date" ? "date" : "text"}
          min={field.min ?? undefined}
          max={field.max ?? undefined}
          step={field.type === "integer" ? 1 : field.type === "number" ? "any" : undefined}
          value={String(value ?? "")}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.type.endsWith("_list") ? "Comma-separated values" : undefined}
        />
      )}
    </label>
  );
}

function DataFetchPanel({
  rows,
  loading,
  busy,
  message,
  rateLimit,
  onRefresh,
  onRun,
}: {
  rows: FetchStatusRow[];
  loading: boolean;
  busy: boolean;
  message: string;
  rateLimit?: RateLimitStatus;
  onRefresh: () => void;
  onRun: () => void;
}) {
  const rateLimitMessage = describeRateLimit(rateLimit);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
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
      {rateLimitMessage ? <p className="text-xs text-amber-300">{rateLimitMessage}</p> : null}
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
    <div className="space-y-3">
      <div>
        <p className="text-slate-300">Backend roots, source files, and symbol catalog are static manifest values in this screen.</p>
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
