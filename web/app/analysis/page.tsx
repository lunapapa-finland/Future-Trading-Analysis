"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { ApiError, postAnalysis, postInsights } from "@/lib/api";
import { fetchConfig } from "@/lib/config";
import { AnalysisSeriesPoint, InsightsResponse } from "@/lib/types";
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

function localYearMonth(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

const metricOptions = [
  { value: "rolling_win_rate", label: "Rolling Win Rate" },
  { value: "drawdown", label: "Drawdown" },
  { value: "pnl_growth", label: "PnL Growth" },
  { value: "sharpe_ratio", label: "Sharpe Ratio" },
  { value: "trade_efficiency", label: "Trade Efficiency" },
  { value: "behavioral_heatmap", label: "Behavioral Heatmap" }
];

export default function AnalysisPage() {
  const [mode, setMode] = useState<"core" | "advanced">("core");
  const [metric, setMetric] = useState(metricOptions[0].value);
  const [window, setWindow] = useState(7);
  const [symbol, setSymbol] = useState<string>("");
  const [coreStartDate, setCoreStartDate] = useState<string>("");
  const [coreEndDate, setCoreEndDate] = useState<string>("");
  const [insightsMinTrades, setInsightsMinTrades] = useState(3);
  const [insightsMonth, setInsightsMonth] = useState(localYearMonth());
  const [showRuleOverrides, setShowRuleOverrides] = useState(false);
  const [maxTradesPerDay, setMaxTradesPerDay] = useState(8);
  const [maxConsecutiveLosses, setMaxConsecutiveLosses] = useState(3);
  const [maxDailyLoss, setMaxDailyLoss] = useState(500);
  const [bigLossThreshold, setBigLossThreshold] = useState(200);
  const [maxTradesAfterBigLoss, setMaxTradesAfterBigLoss] = useState(2);
  const [setupFilter, setSetupFilter] = useState("");
  const [breachesOnly, setBreachesOnly] = useState(false);
  const [defaultsHydrated, setDefaultsHydrated] = useState(false);

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

  useEffect(() => {
    if (defaultsHydrated || !config?.insights_defaults?.rule_compliance) return;
    const d = config.insights_defaults.rule_compliance;
    if (typeof d.max_trades_per_day === "number") setMaxTradesPerDay(d.max_trades_per_day);
    if (typeof d.max_consecutive_losses === "number") setMaxConsecutiveLosses(d.max_consecutive_losses);
    if (typeof d.max_daily_loss === "number") setMaxDailyLoss(d.max_daily_loss);
    if (typeof d.big_loss_threshold === "number") setBigLossThreshold(d.big_loss_threshold);
    if (typeof d.max_trades_after_big_loss === "number") setMaxTradesAfterBigLoss(d.max_trades_after_big_loss);
    setDefaultsHydrated(true);
  }, [config, defaultsHydrated]);

  const { data, isFetching, error } = useQuery({
    queryKey: ["analysis", metric, window, symbol, coreStartDate, coreEndDate, mode],
    queryFn: () =>
      postAnalysis(metric, {
        granularity: "1W-MON",
        window,
        symbol,
        start_date: coreStartDate,
        end_date: coreEndDate,
      }),
    enabled: Boolean(symbol) && mode === "core",
    staleTime: 60_000,
    refetchOnWindowFocus: false
  });

  const preview = useMemo(() => data ?? [], [data]);

  const insightsParams = useMemo(() => {
    const params: Record<string, unknown> = {
      min_trades: insightsMinTrades,
    };
    if (insightsMonth) params.month = insightsMonth;
    if (showRuleOverrides) {
      params.max_trades_per_day = maxTradesPerDay;
      params.max_consecutive_losses = maxConsecutiveLosses;
      params.max_daily_loss = maxDailyLoss;
      params.big_loss_threshold = bigLossThreshold;
      params.max_trades_after_big_loss = maxTradesAfterBigLoss;
    }
    return params;
  }, [
    insightsMinTrades,
    insightsMonth,
    showRuleOverrides,
    maxTradesPerDay,
    maxConsecutiveLosses,
    maxDailyLoss,
    bigLossThreshold,
    maxTradesAfterBigLoss,
  ]);

  const { data: insights, isFetching: insightsFetching, error: insightsError } = useQuery<InsightsResponse>({
    queryKey: ["insights", symbol, insightsMonth, insightsParams, mode],
    queryFn: () =>
      postInsights({
        symbol,
        params: insightsParams,
      }),
    enabled: Boolean(symbol) && mode === "advanced",
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const showWindow =
    metric === "rolling_win_rate" || metric === "sharpe_ratio" || metric === "trade_efficiency";
  const insightsNoData = insightsError instanceof ApiError && insightsError.code === "EMPTY_DATASET";

  return (
    <AppShell active="/analysis">
      <div className="grid gap-4 lg:grid-cols-[1fr_280px]">
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

            <fieldset className="flex flex-col gap-2 rounded-lg border border-white/10 bg-white/5 p-2 sm:col-span-2">
              <legend className="px-1 text-xs uppercase tracking-[0.14em] text-slate-300">Mode</legend>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className={`rounded-md px-3 py-1.5 text-sm ${
                    mode === "core"
                      ? "bg-accent text-white"
                      : "border border-white/15 bg-transparent text-slate-300"
                  }`}
                  onClick={() => setMode("core")}
                >
                  Core Analysis
                </button>
                <button
                  type="button"
                  className={`rounded-md px-3 py-1.5 text-sm ${
                    mode === "advanced"
                      ? "bg-accent text-white"
                      : "border border-white/15 bg-transparent text-slate-300"
                  }`}
                  onClick={() => setMode("advanced")}
                >
                  Advanced Insights
                </button>
              </div>
            </fieldset>

            {mode === "core" ? (
              <>
                <label className="flex flex-col gap-1 text-sm text-slate-300">
                  Start
                  <input
                    type="date"
                    className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                    value={coreStartDate}
                    onChange={(e) => setCoreStartDate(e.target.value)}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm text-slate-300">
                  End
                  <input
                    type="date"
                    className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                    value={coreEndDate}
                    onChange={(e) => setCoreEndDate(e.target.value)}
                  />
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
                {showWindow ? (
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
                ) : null}
              </>
            ) : (
              <>
                <label className="flex flex-col gap-1 text-sm text-slate-300">
                  Min Trades
                  <input
                    type="number"
                    min={1}
                    className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                    value={insightsMinTrades}
                    onChange={(e) => setInsightsMinTrades(Math.max(1, Number(e.target.value) || 1))}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm text-slate-300">
                  Month (optional)
                  <input
                    type="month"
                    className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                    value={insightsMonth}
                    onChange={(e) => setInsightsMonth(e.target.value)}
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm text-slate-300">
                  Setup Filter
                  <input
                    type="text"
                    placeholder="e.g. ORB"
                    className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                    value={setupFilter}
                    onChange={(e) => setSetupFilter(e.target.value)}
                  />
                </label>
                <label className="flex items-center gap-2 text-sm text-slate-300 sm:mt-6">
                  <input
                    type="checkbox"
                    checked={breachesOnly}
                    onChange={(e) => setBreachesOnly(e.target.checked)}
                  />
                  Show breached days only
                </label>
                <details className="sm:col-span-2">
                  <summary className="cursor-pointer text-sm text-slate-300">Advanced Options (Rule Overrides)</summary>
                  <div className="mt-2 grid gap-3 sm:grid-cols-2">
                    <label className="flex items-center gap-2 text-sm text-slate-300 sm:col-span-2">
                      <input
                        type="checkbox"
                        checked={showRuleOverrides}
                        onChange={(e) => setShowRuleOverrides(e.target.checked)}
                      />
                      Enable custom rule thresholds
                    </label>
                    <label className="flex flex-col gap-1 text-sm text-slate-300">
                      Max Trades / Day
                      <input
                        type="number"
                        min={1}
                        disabled={!showRuleOverrides}
                        className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent disabled:opacity-50"
                        value={maxTradesPerDay}
                        onChange={(e) => setMaxTradesPerDay(Math.max(1, Number(e.target.value) || 1))}
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-sm text-slate-300">
                      Max Consecutive Losses
                      <input
                        type="number"
                        min={1}
                        disabled={!showRuleOverrides}
                        className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent disabled:opacity-50"
                        value={maxConsecutiveLosses}
                        onChange={(e) => setMaxConsecutiveLosses(Math.max(1, Number(e.target.value) || 1))}
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-sm text-slate-300">
                      Max Daily Loss
                      <input
                        type="number"
                        min={1}
                        disabled={!showRuleOverrides}
                        className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent disabled:opacity-50"
                        value={maxDailyLoss}
                        onChange={(e) => setMaxDailyLoss(Math.max(1, Number(e.target.value) || 1))}
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-sm text-slate-300">
                      Big Loss Threshold
                      <input
                        type="number"
                        min={1}
                        disabled={!showRuleOverrides}
                        className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent disabled:opacity-50"
                        value={bigLossThreshold}
                        onChange={(e) => setBigLossThreshold(Math.max(1, Number(e.target.value) || 1))}
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-sm text-slate-300">
                      Max Trades After Big Loss
                      <input
                        type="number"
                        min={1}
                        disabled={!showRuleOverrides}
                        className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent disabled:opacity-50"
                        value={maxTradesAfterBigLoss}
                        onChange={(e) => setMaxTradesAfterBigLoss(Math.max(1, Number(e.target.value) || 1))}
                      />
                    </label>
                  </div>
                </details>
              </>
            )}
          </div>
        </Card>
        <Card title="Status">
          <div className="text-sm text-slate-300">
            <p>Mode: {mode === "core" ? "Core Analysis" : "Advanced Insights"}</p>
            <p>Symbol: {symbol || ""}</p>
            {mode === "core" ? (
              <>
                <p>Metric: {metric}</p>
                <p>
                  Range: {coreStartDate || "(start)"} → {coreEndDate || "(end)"}
                </p>
                {showWindow ? <p>Window: {window}</p> : null}
                {isFetching ? <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Loading…</p> : null}
                {error ? <p className="text-red-300">Error: {(error as Error).message}</p> : null}
              </>
            ) : (
              <>
                <p>Min Trades: {insightsMinTrades}</p>
                <p>Month: {insightsMonth}</p>
                {insightsFetching ? <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Computing insights…</p> : null}
                {insightsError && !insightsNoData ? (
                  <p className="text-red-300">Error: {(insightsError as Error).message}</p>
                ) : null}
              </>
            )}
            {configLoading && <p className="text-xs text-slate-400">Loading symbols…</p>}
            {configError && <p className="text-xs text-red-300">Config error: {(configError as Error).message}</p>}
          </div>
        </Card>
      </div>

      {mode === "core" ? (
        <Card title="Visualization" className="mt-2">
          <div className="overflow-x-auto">
            <div className="min-w-full md:min-w-[900px]">
              {preview.length === 0 ? (
                <p className="text-slate-400">No data yet.</p>
              ) : (
                <AnalysisChart metric={metric} points={preview} />
              )}
            </div>
          </div>
        </Card>
      ) : (
        <Card title="Advanced Insights" className="mt-2">
          {insightsFetching ? <p className="text-slate-400">Computing insights…</p> : null}
          {insightsNoData ? <p className="text-slate-400">No data for the selected symbol/month.</p> : null}
          {insightsError && !insightsNoData ? (
            <p className="text-red-300">Error: {(insightsError as Error).message}</p>
          ) : null}
          {insights ? <InsightsPanel insights={insights} setupFilter={setupFilter} breachesOnly={breachesOnly} /> : null}
        </Card>
      )}
    </AppShell>
  );
}

function InsightsPanel({
  insights,
  setupFilter,
  breachesOnly,
}: {
  insights: InsightsResponse;
  setupFilter: string;
  breachesOnly: boolean;
}) {
  const normalizedSetupFilter = setupFilter.trim().toLowerCase();
  const setupRows = (insights.setup_journal ?? []).filter((row) => {
    if (!normalizedSetupFilter) return true;
    const setup = String((row as Record<string, unknown>).Setup ?? "").toLowerCase();
    return setup.includes(normalizedSetupFilter);
  });
  const compliance = insights.rule_compliance?.summary ?? {};
  const complianceDaily = (insights.rule_compliance?.daily ?? []).filter((row) => {
    if (!breachesOnly) return true;
    const count = Number((row as Record<string, unknown>).BreachCount ?? 0);
    return count > 0;
  });
  const maeMfeOverall = insights.mae_mfe?.overall ?? {};
  const maeMfeBySetup = (insights.mae_mfe?.by_setup ?? []).filter((row) => {
    if (!normalizedSetupFilter) return true;
    const setup = String((row as Record<string, unknown>).Setup ?? "").toLowerCase();
    return setup.includes(normalizedSetupFilter);
  });
  const playbookHighlights = insights.playbook?.highlights ?? [];
  const playbookStop = insights.playbook?.stop_doing ?? [];
  const playbookActions = insights.playbook?.action_items ?? [];
  const monthlySummary = insights.monthly_report?.summary ?? {};
  const monthlyFocus = insights.monthly_report?.focus_points ?? [];
  const monthlyMarkdown = insights.monthly_report?.markdown ?? "";

  return (
    <div className="grid gap-4">
      <div>
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Setup Journal</h3>
        <SimpleTable rows={setupRows} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Rule Compliance Score</h3>
          <SimpleKv kv={compliance} />
          <div className="mt-2">
            <SimpleTable rows={complianceDaily.slice(-10)} />
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">MAE / MFE Analytics</h3>
          <SimpleKv kv={maeMfeOverall} />
          <div className="mt-2">
            <SimpleTable rows={maeMfeBySetup} />
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Playbook Builder</h3>
          <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Highlights</p>
          <SimpleTable rows={playbookHighlights} />
          <p className="mb-1 mt-3 text-xs uppercase tracking-[0.15em] text-slate-400">Stop Doing</p>
          <SimpleTable rows={playbookStop} />
          <p className="mb-1 mt-3 text-xs uppercase tracking-[0.15em] text-slate-400">Action Items</p>
          <SimpleTable rows={playbookActions} />
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Monthly Review Report</h3>
          <SimpleKv kv={monthlySummary} />
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-300">
            {monthlyFocus.map((line, idx) => (
              <li key={`${idx}-${line}`}>{line}</li>
            ))}
          </ul>
          {monthlyMarkdown ? (
            <details className="mt-3 rounded-lg border border-white/10 bg-white/5 p-2">
              <summary className="cursor-pointer text-xs uppercase tracking-[0.15em] text-slate-300">Auto Report (Markdown)</summary>
              <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-300">{monthlyMarkdown}</pre>
            </details>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function SimpleKv({ kv }: { kv: Record<string, string | number> }) {
  const entries = Object.entries(kv ?? {});
  if (!entries.length) return <p className="text-slate-400">No data.</p>;
  return (
    <div className="grid grid-cols-1 gap-x-3 gap-y-1 text-sm sm:grid-cols-2">
      {entries.map(([k, v]) => (
        <React.Fragment key={k}>
          <div className="text-slate-400">{k}</div>
          <div className="text-left text-slate-200 sm:text-right">{String(v)}</div>
        </React.Fragment>
      ))}
    </div>
  );
}

function SimpleTable({ rows }: { rows: AnalysisSeriesPoint[] }) {
  if (!rows || rows.length === 0) return <p className="text-slate-400">No data.</p>;
  const headers = Object.keys(rows[0] ?? {});
  const visibleRows = rows.slice(0, 12);
  return (
    <>
      <div className="space-y-2 md:hidden">
        {visibleRows.map((row, idx) => (
          <div key={idx} className="rounded-lg border border-white/10 bg-white/5 p-2">
            {headers.map((h) => (
              <div key={h} className="grid grid-cols-[110px_1fr] gap-2 py-0.5 text-xs">
                <span className="text-slate-400">{h}</span>
                <span className="break-words text-slate-200">{String((row as any)[h] ?? "")}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="hidden overflow-x-auto rounded-lg border border-white/10 md:block">
        <table className="min-w-full text-xs">
        <thead className="bg-white/5 text-slate-300">
          <tr>
            {headers.map((h) => (
              <th key={h} className="px-2 py-1 text-left font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {visibleRows.map((row, idx) => (
            <tr key={idx} className="border-t border-white/10 text-slate-200">
              {headers.map((h) => (
                <td key={h} className="px-2 py-1">
                  {String((row as any)[h] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
        </table>
      </div>
    </>
  );
}

function AnalysisChart({ metric, points }: { metric: string; points: AnalysisSeriesPoint[] }) {
  if (metric === "behavioral_heatmap") {
    const days = Array.from(new Set(points.map((p: any) => p.DayOfWeek || "")));
    const hours = Array.from(new Set(points.map((p: any) => p.HourOfDay || 0))).sort((a, b) => a - b);
    const values = points.map((p: any) => Number(p["PnL(Net)"] || 0));
    const maxAbs = Math.max(...values.map((v) => Math.abs(v)), 1);
    const cellMap = new Map<string, number>();
    (points as any[]).forEach((p) => {
      cellMap.set(`${p.HourOfDay}|${p.DayOfWeek}`, Number(p["PnL(Net)"] || 0));
    });
    return (
      <div className="overflow-auto">
        <div className="grid min-w-[640px]" style={{ gridTemplateColumns: `90px repeat(${days.length}, minmax(70px,1fr))` }}>
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
                const val = cellMap.get(`${h}|${d}`) ?? 0;
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

  const labels = points.map((p: any) => {
    const raw = p.Period ?? p.TradeDay ?? p.Date ?? p.DateHour ?? p.TradeIndex ?? p.HourlyIndex ?? "";
    return String(raw);
  });
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
