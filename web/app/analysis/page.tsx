"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { postAnalysis } from "@/lib/api";
import { fetchConfig } from "@/lib/config";
import { AnalysisSeriesPoint } from "@/lib/types";
import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Line } from "react-chartjs-2";
import React from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const metricOptions = [
  { value: "rolling_win_rate", label: "Rolling Win Rate" },
  { value: "drawdown", label: "Drawdown" },
  { value: "pnl_growth", label: "PnL Growth" },
  { value: "sharpe_ratio", label: "Sharpe Ratio" },
  { value: "trade_efficiency", label: "Trade Efficiency" },
  { value: "behavioral_heatmap", label: "Behavioral Heatmap" }
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
  const [symbol, setSymbol] = useState<string>("");
  const [startDate, setStartDate] = useState<string>("");
  const [endDate, setEndDate] = useState<string>("");

  const { data: config, isLoading: configLoading, error: configError } = useQuery({
    queryKey: ["config"],
    queryFn: fetchConfig,
    staleTime: 5 * 60_000
  });

  useEffect(() => {
    if (!symbol && config?.symbols?.length) {
      setSymbol(config.symbols[0].symbol);
    }
  }, [config, symbol]);

  const { data, isFetching, error } = useQuery({
    queryKey: ["analysis", metric, granularity, window, symbol, startDate, endDate],
    queryFn: () => postAnalysis(metric, { granularity, window, symbol, start_date: startDate, end_date: endDate }),
    enabled: Boolean(symbol),
    staleTime: 60_000,
    refetchOnWindowFocus: false
  });

  const preview = useMemo(() => data ?? [], [data]);

  return (
    <AppShell active="/analysis">
      <div className="grid gap-4 md:grid-cols-[1fr_280px]">
        <Card title="Controls">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-1 text-sm text-slate-300">
              Symbol
              <select
                className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                disabled={configLoading}
              >
                {config?.symbols?.map((s) => (
                  <option key={s.symbol} value={s.symbol}>
                    {s.symbol}
                  </option>
                ))}
              </select>
              {configError ? <span className="text-xs text-red-300">Failed to load symbols</span> : null}
            </label>
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
            <label className="flex flex-col gap-1 text-sm text-slate-300">
              Start
              <input
                type="date"
                className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm text-slate-300">
              End
              <input
                type="date"
                className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
              />
            </label>
          </div>
        </Card>
        <Card title="Status">
          <div className="text-sm text-slate-300">
            <p>Metric: {metric}</p>
            <p>Granularity: {granularity}</p>
            <p>Window: {window}</p>
            <p>Symbol: {symbol || ""}</p>
            <p>
              Range: {startDate || "(start)"} → {endDate || "(end)"}
            </p>
            {isFetching && <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Loading…</p>}
            {error && <p className="text-red-300">Error: {(error as Error).message}</p>}
            {configLoading && <p className="text-xs text-slate-400">Loading symbols…</p>}
            {configError && <p className="text-xs text-red-300">Config error: {(configError as Error).message}</p>}
          </div>
        </Card>
      </div>

      <Card title="Visualization" className="mt-2">
        <div className="overflow-x-auto">
          <div className="min-w-[900px]">
            {preview.length === 0 ? (
              <p className="text-slate-400">No data yet.</p>
            ) : (
              <AnalysisChart metric={metric} points={preview} />
            )}
          </div>
        </div>
      </Card>
    </AppShell>
  );
}

function AnalysisChart({ metric, points }: { metric: string; points: AnalysisSeriesPoint[] }) {
  if (metric === "behavioral_heatmap") {
    const days = Array.from(new Set(points.map((p: any) => p.DayOfWeek || "")));
    const hours = Array.from(new Set(points.map((p: any) => p.HourOfDay || 0))).sort((a, b) => a - b);
    const values = points.map((p: any) => Number(p["PnL(Net)"] || 0));
    const maxAbs = Math.max(...values.map((v) => Math.abs(v)), 1);
    return (
      <div className="overflow-auto">
        <div className="grid" style={{ gridTemplateColumns: `100px repeat(${days.length}, minmax(80px,1fr))` }}>
          <div className="text-xs text-slate-400">Hour</div>
          {days.map((d) => (
            <div key={d} className="text-center text-xs text-slate-300">
              {d}
            </div>
          ))}
          {hours.map((h) => (
            <React.Fragment key={h}>
              <div className="text-xs text-slate-400">{h}:00</div>
              {days.map((d) => {
                const row = (points as any).find((p: any) => p.HourOfDay === h && p.DayOfWeek === d);
                const val = row ? Number(row["PnL(Net)"] || 0) : 0;
                const intensity = Math.min(Math.abs(val) / maxAbs, 1);
                const color = val >= 0 ? `rgba(34,197,94,${0.1 + 0.5 * intensity})` : `rgba(239,68,68,${0.1 + 0.5 * intensity})`;
                return (
                  <div
                    key={`${h}-${d}`}
                    className="flex items-center justify-center text-xs text-white"
                    style={{ backgroundColor: color, minHeight: "32px" }}
                    title={`${d} ${h}:00 | PnL ${val.toFixed(2)}`}
                  >
                    {val.toFixed(0)}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    );
  }

  const labels = points.map((p) => p.Period ?? p.TradeDay ?? p.Date ?? "");
  const values = points.map((p: any) => {
    if (metric === "drawdown") return p.Drawdown ?? 0;
    if (metric === "pnl_growth") return p.CumulativePnL ?? p.NetPnL ?? 0;
    if (metric === "rolling_win_rate") return p.WinRate ?? 0;
    if (metric === "sharpe_ratio") return p.SharpeRatio ?? 0;
    if (metric === "trade_efficiency") return p.Efficiency ?? 0;
    return 0;
  });

  const data = {
    labels,
    datasets: [
      {
        label: metric,
        data: values,
        borderColor: "#22c55e",
        backgroundColor: "rgba(34,197,94,0.2)",
        tension: 0.1,
      },
    ],
  };

  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: { mode: "index" as const, intersect: false },
      title: { display: false },
    },
    scales: {
      x: { ticks: { color: "#e2e8f0" }, grid: { color: "rgba(226,232,240,0.1)" } },
      y: { ticks: { color: "#e2e8f0" }, grid: { color: "rgba(226,232,240,0.1)" } },
    },
  };

  return <Line data={data} options={options} />;
}
