"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { postAnalysis } from "@/lib/api";
import { AnalysisSeriesPoint } from "@/lib/types";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

const metricOptions = [
  { value: "rolling_win_rate", label: "Rolling Win Rate" },
  { value: "drawdown", label: "Drawdown" },
  { value: "pnl_growth", label: "PnL Growth" },
  { value: "sharpe_ratio", label: "Sharpe Ratio" },
  { value: "trade_efficiency", label: "Trade Efficiency" }
];

const granularityOptions = [
  { value: "1D", label: "Daily" },
  { value: "1W-MON", label: "Weekly" },
  { value: "1M", label: "Monthly" }
];

export default function AnalysisPage() {
  const [metric, setMetric] = useState(metricOptions[0].value);
  const [granularity, setGranularity] = useState("1W-MON");
  const [window, setWindow] = useState(7);

  const { data, isFetching, error } = useQuery({
    queryKey: ["analysis", metric, granularity, window],
    queryFn: () => postAnalysis(metric, { granularity, window }),
    staleTime: 60_000,
    refetchOnWindowFocus: false
  });

  const preview = useMemo(() => {
    return (data ?? []).slice(0, 5);
  }, [data]);

  return (
    <AppShell active="/analysis">
      <div className="grid gap-4 md:grid-cols-[1fr_280px]">
        <Card title="Controls">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm text-slate-300">
              Metric
              <select
                className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
              >
                {metricOptions.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-300">
              Granularity
              <select
                className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                value={granularity}
                onChange={(e) => setGranularity(e.target.value)}
              >
                {granularityOptions.map((g) => (
                  <option key={g.value} value={g.value}>
                    {g.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-300">
              Window
              <input
                type="number"
                min={1}
                className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                value={window}
                onChange={(e) => setWindow(Number(e.target.value))}
              />
            </label>
          </div>
        </Card>
        <Card title="Status">
          <div className="text-sm text-slate-300">
            <p>Metric: {metric}</p>
            <p>Granularity: {granularity}</p>
            <p>Window: {window}</p>
            {isFetching && <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Loading…</p>}
            {error && <p className="text-red-300">Error: {(error as Error).message}</p>}
          </div>
        </Card>
      </div>

      <Card title="Preview (first 5 rows)" className="mt-2">
        {preview.length === 0 ? (
          <p className="text-slate-400">No data yet.</p>
        ) : (
          <pre className="overflow-x-auto rounded-lg bg-black/40 p-3 text-xs text-slate-200">
            {JSON.stringify(preview, null, 2)}
          </pre>
        )}
        <p className="mt-2 text-xs text-slate-400">
          Next steps: map each metric to tailored chart types (line/area/heatmap) mirroring Dash callbacks.
        </p>
      </Card>
    </AppShell>
  );
}
