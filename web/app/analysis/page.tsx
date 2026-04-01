"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { ApiError, postAnalysis, postInsights } from "@/lib/api";
import { fetchConfig } from "@/lib/config";
import { AnalysisSeriesPoint, InsightsResponse } from "@/lib/types";
import { useMemo, useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, Chart, Line, Scatter } from "react-chartjs-2";
import React from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, Title, Tooltip, Legend);

function localYearMonth(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  return `${year}-${month}`;
}

function localDateYmd(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function localMonthStartYmd(): string {
  const now = new Date();
  return localDateYmd(new Date(now.getFullYear(), now.getMonth(), 1));
}

function localTodayYmd(): string {
  return localDateYmd(new Date());
}

const metricOptions = [
  { value: "rolling_win_rate", label: "Rolling Win Rate" },
  { value: "drawdown", label: "Drawdown" },
  { value: "pnl_growth", label: "PnL Growth" },
  { value: "pnl_distribution", label: "PnL Distribution" },
  { value: "behavioral_patterns", label: "Behavioral Patterns (AvgPnL/Size)" },
  { value: "hourly_performance", label: "Hourly Performance" },
  { value: "overtrading_detection", label: "Overtrading Detection" },
  { value: "kelly_criterion", label: "Kelly Criterion" },
  { value: "performance_envelope", label: "Performance Envelope" },
  { value: "sharpe_ratio", label: "Sharpe Ratio" },
  { value: "trade_efficiency", label: "Trade Efficiency" },
  { value: "behavioral_heatmap", label: "Behavioral Heatmap (Total PnL)" }
];

const granularityOptions = [
  { value: "1D", label: "Daily (1D)" },
  { value: "1W-MON", label: "Weekly (1W-MON)" },
  { value: "1M", label: "Monthly (1M)" },
];

const metricHelp: Record<
  string,
  { x: string; y: string; calc: string; usage: string }
> = {
  rolling_win_rate: {
    x: "Trade index (time-ordered exits)",
    y: "Rolling win rate (%)",
    calc: "Wins / trades inside the selected window.",
    usage: "Use for short-term consistency drift.",
  },
  drawdown: {
    x: "Period (by selected granularity)",
    y: "Drawdown from running peak PnL",
    calc: "CumulativePnL - max(CumulativePnL, baseline 0).",
    usage: "Use to monitor pain depth and recovery.",
  },
  pnl_growth: {
    x: "Period (by selected granularity)",
    y: "Cumulative strategy PnL and passive benchmark",
    calc: "Strategy cumulative net PnL vs passive compounded growth.",
    usage: "Use to compare active edge vs passive baseline.",
  },
  pnl_distribution: {
    x: "PnL bins (ranges)",
    y: "Trade count per bin",
    calc: "Histogram of per-trade PnL(Net).",
    usage: "Use to inspect fat tails and skew.",
  },
  behavioral_patterns: {
    x: "Hour + weekday matrix",
    y: "AvgPnL normalized by total size",
    calc: "AvgPnL = TotalPnL / TotalSize per cell; includes TradeCount.",
    usage: "Use for efficiency by session timing.",
  },
  behavioral_heatmap: {
    x: "Hour + weekday matrix",
    y: "Total PnL(Net) per cell",
    calc: "Summed PnL(Net) by HourOfDay and DayOfWeek.",
    usage: "Use for gross contribution hotspots.",
  },
  hourly_performance: {
    x: "Hour of day (0-23)",
    y: "Average PnL per trade in each hour bucket",
    calc: "Group all selected trades by EnteredAt hour; HourlyPnL = TotalPnL / TradeCount.",
    usage: "Use to find statistically stronger/weaker intraday hours.",
  },
  overtrading_detection: {
    x: "Daily and trade-level views",
    y: "Trades/day, DailyPnL, and trade R-multiple",
    calc: "Applies big-loss and post-loss overtrading tagging rules.",
    usage: "Use to diagnose revenge/overtrading behavior.",
  },
  kelly_criterion: {
    x: "TradeDay",
    y: "Kelly value",
    calc: "Uses daily win rate and reward/risk estimates.",
    usage: "Use as sizing sanity signal, not a standalone trigger.",
  },
  performance_envelope: {
    x: "Winning Rate (%)",
    y: "Win/Loss ratio",
    calc: "Actual period points vs theoretical break-even envelope.",
    usage: "Use to see if your win/loss mix is above theoretical line.",
  },
  sharpe_ratio: {
    x: "TradeDay",
    y: "Rolling Sharpe ratio",
    calc: "Annualized mean excess return / annualized return std.",
    usage: "Use for risk-adjusted stability.",
  },
  trade_efficiency: {
    x: "Trade index (time-ordered exits)",
    y: "Rolling PnL per hour held",
    calc: "Per-trade efficiency = PnL / duration hours, then rolling mean.",
    usage: "Use to check execution quality vs holding time.",
  },
};

export default function AnalysisPage() {
  const [mode, setMode] = useState<"core" | "advanced">("core");
  const [metric, setMetric] = useState(metricOptions[0].value);
  const [coreGranularity, setCoreGranularity] = useState("1D");
  const [window, setWindow] = useState(7);
  const [symbol, setSymbol] = useState<string>("");
  const [coreStartDate, setCoreStartDate] = useState<string>(localMonthStartYmd());
  const [coreEndDate, setCoreEndDate] = useState<string>(localTodayYmd());
  const [insightsMinTrades, setInsightsMinTrades] = useState(3);
  const [insightsMonth, setInsightsMonth] = useState(localYearMonth());
  const [showRuleOverrides, setShowRuleOverrides] = useState(false);
  const [maxTradesPerDay, setMaxTradesPerDay] = useState(8);
  const [maxConsecutiveLosses, setMaxConsecutiveLosses] = useState(3);
  const [maxDailyLoss, setMaxDailyLoss] = useState(500);
  const [bigLossThreshold, setBigLossThreshold] = useState(200);
  const [maxTradesAfterBigLoss, setMaxTradesAfterBigLoss] = useState(2);
  const [capLossPerTrade, setCapLossPerTrade] = useState(200);
  const [capTradesAfterBigLoss, setCapTradesAfterBigLoss] = useState(5);
  const [phaseFilters, setPhaseFilters] = useState<string[]>([]);
  const [contextFilters, setContextFilters] = useState<string[]>([]);
  const [setupTagFilters, setSetupTagFilters] = useState<string[]>([]);
  const [signalBarFilters, setSignalBarFilters] = useState<string[]>([]);
  const [tradeIntentFilters, setTradeIntentFilters] = useState<string[]>([]);
  const [includeUnmatched, setIncludeUnmatched] = useState(false);
  const [breachesOnly, setBreachesOnly] = useState(false);
  const [defaultsHydrated, setDefaultsHydrated] = useState(false);
  const [tagFiltersHydrated, setTagFiltersHydrated] = useState(false);

  const { data: config, isLoading: configLoading, error: configError } = useQuery({
    queryKey: ["config"],
    queryFn: fetchConfig,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });

  useEffect(() => {
    if (!symbol && config?.symbols?.length) {
      setSymbol(config.symbols[0].symbol);
    }
  }, [config, symbol]);

  useEffect(() => {
    if (defaultsHydrated || !config) return;
    const d = config.insights_defaults?.rule_compliance;
    if (d) {
      if (typeof d.max_trades_per_day === "number") setMaxTradesPerDay(d.max_trades_per_day);
      if (typeof d.max_consecutive_losses === "number") setMaxConsecutiveLosses(d.max_consecutive_losses);
      if (typeof d.max_daily_loss === "number") setMaxDailyLoss(d.max_daily_loss);
      if (typeof d.big_loss_threshold === "number") setBigLossThreshold(d.big_loss_threshold);
      if (typeof d.max_trades_after_big_loss === "number") setMaxTradesAfterBigLoss(d.max_trades_after_big_loss);
    }
    if (typeof config.analysis_defaults?.include_unmatched === "boolean") {
      setIncludeUnmatched(config.analysis_defaults.include_unmatched);
    }
    setDefaultsHydrated(true);
  }, [config, defaultsHydrated]);

  useEffect(() => {
    if (tagFiltersHydrated || !config?.tag_taxonomy) return;
    const phase = (config.tag_taxonomy.phase ?? []).map((x: any) => String(x.value));
    const context = (config.tag_taxonomy.context ?? []).map((x: any) => String(x.value));
    const setup = (config.tag_taxonomy.setup ?? []).map((x: any) => String(x.value));
    const signal = (config.tag_taxonomy.signal_bar ?? []).map((x: any) => String(x.value));
    const intent = (config.tag_taxonomy.trade_intent ?? []).map((x: any) => String(x.value));
    setPhaseFilters(phase);
    setContextFilters(context);
    setSetupTagFilters(setup);
    setSignalBarFilters(signal);
    setTradeIntentFilters(intent);
    setTagFiltersHydrated(true);
  }, [config, tagFiltersHydrated]);

  const { data: analysisRaw, isFetching, error } = useQuery({
    queryKey: [
      "analysis",
      metric,
      window,
      coreGranularity,
      capLossPerTrade,
      capTradesAfterBigLoss,
      includeUnmatched,
      symbol,
      coreStartDate,
      coreEndDate,
      mode,
    ],
    queryFn: () =>
      postAnalysis(metric, {
        granularity: coreGranularity,
        window,
        symbol,
        start_date: coreStartDate,
        end_date: coreEndDate,
        include_unmatched: includeUnmatched,
        params:
          metric === "overtrading_detection"
            ? {
                cap_loss_per_trade: capLossPerTrade,
                cap_trades_after_big_loss: capTradesAfterBigLoss,
              }
            : undefined,
      }),
    enabled: Boolean(symbol) && mode === "core",
    staleTime: 60_000,
    refetchOnWindowFocus: false
  });

  const analysisData = useMemo(() => {
    const raw = analysisRaw as any;
    const envelope = raw && !Array.isArray(raw) && raw.theoretical && raw.actual ? raw : null;
    const overtrading = raw && !Array.isArray(raw) && raw.daily && raw.trades ? raw : null;
    const kelly = raw && !Array.isArray(raw) && raw.data && raw.metadata ? raw : null;
    const series = Array.isArray(raw) ? raw : envelope ? envelope.actual ?? [] : kelly ? kelly.data ?? [] : [];
    return { raw, envelope, overtrading, kelly, series };
  }, [analysisRaw]);

  const insightsParams = useMemo(() => {
    const params: Record<string, unknown> = {
      min_trades: insightsMinTrades,
    };
    if (insightsMonth) params.month = insightsMonth;
    if (phaseFilters.length) params.phase = phaseFilters;
    if (contextFilters.length) params.context = contextFilters;
    if (setupTagFilters.length) params.setup = setupTagFilters;
    if (signalBarFilters.length) params.signal_bar = signalBarFilters;
    if (tradeIntentFilters.length) params.trade_intent = tradeIntentFilters;
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
    phaseFilters,
    contextFilters,
    setupTagFilters,
    signalBarFilters,
    tradeIntentFilters,
  ]);

  const { data: insights, isFetching: insightsFetching, error: insightsError } = useQuery<InsightsResponse>({
    queryKey: ["insights", symbol, insightsMonth, insightsParams, includeUnmatched, mode],
    queryFn: () =>
      postInsights({
        symbol,
        include_unmatched: includeUnmatched,
        params: insightsParams,
      }),
    enabled: Boolean(symbol) && mode === "advanced",
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  const showWindow =
    metric === "rolling_win_rate" ||
    metric === "sharpe_ratio" ||
    metric === "trade_efficiency";
  const showGranularity = metric === "pnl_growth" || metric === "drawdown" || metric === "performance_envelope";
  const hasCoreData =
    metric === "performance_envelope"
      ? Boolean((analysisData.envelope?.theoretical?.length ?? 0) > 0 || (analysisData.envelope?.actual?.length ?? 0) > 0)
      : metric === "overtrading_detection"
        ? Boolean((analysisData.overtrading?.daily?.length ?? 0) > 0 || (analysisData.overtrading?.trades?.length ?? 0) > 0)
        : analysisData.series.length > 0;
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
                {showGranularity ? (
                  <label className="flex flex-col gap-1 text-sm text-slate-300">
                    Granularity
                    <select
                      className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                      value={coreGranularity}
                      onChange={(e) => setCoreGranularity(e.target.value)}
                    >
                      {granularityOptions.map((g) => (
                        <option key={g.value} value={g.value}>
                          {g.label}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
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
                {metric === "overtrading_detection" ? (
                  <>
                    <label className="flex flex-col gap-1 text-sm text-slate-300">
                      Cap Loss / Trade
                      <input
                        type="number"
                        min={1}
                        className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                        value={capLossPerTrade}
                        onChange={(e) => setCapLossPerTrade(Math.max(1, Number(e.target.value) || 1))}
                      />
                    </label>
                    <label className="flex flex-col gap-1 text-sm text-slate-300">
                      Trades After Big Loss
                      <input
                        type="number"
                        min={1}
                        className="rounded-lg border border-white/10 bg-surface px-3 py-2 text-white outline-none focus:border-accent"
                        value={capTradesAfterBigLoss}
                        onChange={(e) => setCapTradesAfterBigLoss(Math.max(1, Number(e.target.value) || 1))}
                      />
                    </label>
                  </>
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
                <div className="flex flex-col gap-1 text-sm text-slate-300">
                  <span>Phase Filter (multi)</span>
                  <CheckboxPills options={(config?.tag_taxonomy?.phase ?? []).map((x: any) => String(x.value))} selected={phaseFilters} onChange={setPhaseFilters} />
                </div>
                <div className="flex flex-col gap-1 text-sm text-slate-300">
                  <span>Context Filter (multi)</span>
                  <CheckboxPills options={(config?.tag_taxonomy?.context ?? []).map((x: any) => String(x.value))} selected={contextFilters} onChange={setContextFilters} />
                </div>
                <div className="flex flex-col gap-1 text-sm text-slate-300 sm:col-span-2">
                  <span>Setup Tag Filter (multi)</span>
                  <CheckboxPills options={(config?.tag_taxonomy?.setup ?? []).map((x: any) => String(x.value))} selected={setupTagFilters} onChange={setSetupTagFilters} />
                </div>
                <div className="flex flex-col gap-1 text-sm text-slate-300 sm:col-span-2">
                  <span>SignalBar Filter (multi)</span>
                  <CheckboxPills options={(config?.tag_taxonomy?.signal_bar ?? []).map((x: any) => String(x.value))} selected={signalBarFilters} onChange={setSignalBarFilters} />
                </div>
                <div className="flex flex-col gap-1 text-sm text-slate-300 sm:col-span-2">
                  <span>Trade Intent Filter (multi)</span>
                  <CheckboxPills options={(config?.tag_taxonomy?.trade_intent ?? []).map((x: any) => String(x.value))} selected={tradeIntentFilters} onChange={setTradeIntentFilters} />
                </div>
                <label className="flex items-center gap-2 text-sm text-slate-300 sm:mt-6">
                  <input
                    type="checkbox"
                    checked={includeUnmatched}
                    onChange={(e) => setIncludeUnmatched(e.target.checked)}
                  />
                  Include unmatched trades
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
                {metricHelp[metric] ? (
                  <div className="mt-2 space-y-1 rounded-lg border border-white/10 bg-white/5 p-2 text-xs text-slate-300">
                    <p><span className="text-slate-400">X:</span> {metricHelp[metric].x}</p>
                    <p><span className="text-slate-400">Y:</span> {metricHelp[metric].y}</p>
                    <p><span className="text-slate-400">Calc:</span> {metricHelp[metric].calc}</p>
                    <p><span className="text-slate-400">Use:</span> {metricHelp[metric].usage}</p>
                  </div>
                ) : null}
                <p>
                  Range: {coreStartDate || "(start)"} → {coreEndDate || "(end)"}
                </p>
                {showGranularity ? <p>Granularity: {coreGranularity}</p> : null}
                {showWindow ? <p>Window: {window}</p> : null}
                <p>Include unmatched: {includeUnmatched ? "Yes" : "No (default)"}</p>
                {metric === "overtrading_detection" ? (
                  <>
                    <p>Cap Loss / Trade: {capLossPerTrade}</p>
                    <p>Trades After Big Loss: {capTradesAfterBigLoss}</p>
                  </>
                ) : null}
                {isFetching ? <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Loading…</p> : null}
                {error ? <p className="text-red-300">Error: {(error as Error).message}</p> : null}
              </>
            ) : (
              <>
                <p>Min Trades: {insightsMinTrades}</p>
                <p>Month: {insightsMonth}</p>
                <p>Include unmatched: {includeUnmatched ? "Yes" : "No (default)"}</p>
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
              {!hasCoreData ? (
                <p className="text-slate-400">No data yet.</p>
              ) : metric === "overtrading_detection" && analysisData.overtrading ? (
                <OvertradingPanel
                  daily={(analysisData.overtrading.daily ?? []) as AnalysisSeriesPoint[]}
                  trades={(analysisData.overtrading.trades ?? []) as AnalysisSeriesPoint[]}
                />
              ) : (
                <AnalysisChart metric={metric} points={analysisData.series} envelopeData={analysisData.envelope} />
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
          {insights ? <InsightsPanel insights={insights} breachesOnly={breachesOnly} /> : null}
        </Card>
      )}
    </AppShell>
  );
}

function InsightsPanel({
  insights,
  breachesOnly,
}: {
  insights: InsightsResponse;
  breachesOnly: boolean;
}) {
  const setupRows = insights.setup_journal ?? [];
  const appliedConfig = (insights.applied_config ?? {}) as Record<string, unknown>;
  const analysisScope = (insights.analysis_scope ?? {}) as Record<string, string | number>;
  const setupQualityRaw = (insights.setup_quality ?? {}) as Record<string, unknown>;
  const setupSourceCounts = ((setupQualityRaw.SourceCounts as Record<string, number>) ?? {});
  const setupQuality = Object.fromEntries(
    Object.entries(setupQualityRaw).filter(([k]) => k !== "SourceCounts"),
  ) as Record<string, string | number>;
  const setupSourceRows = Object.entries(setupSourceCounts).map(([source, count]) => ({ Source: source, Count: count }));
  const compliance = insights.rule_compliance?.summary ?? {};
  const complianceDaily = (insights.rule_compliance?.daily ?? []).filter((row) => {
    if (!breachesOnly) return true;
    const count = Number((row as Record<string, unknown>).BreachCount ?? 0);
    return count > 0;
  });
  const qualityByEntryHour = insights.execution_quality?.by_entry_hour ?? [];
  const qualityByHoldBucket = insights.execution_quality?.by_hold_bucket ?? [];
  const playbookHighlights = insights.playbook?.highlights ?? [];
  const playbookStop = insights.playbook?.stop_doing ?? [];
  const playbookActions = insights.playbook?.action_items ?? [];
  const playbookRationale = insights.playbook?.rationale;
  const dayPlanSummary = insights.day_plan_review?.summary ?? {};
  const dayPlanDaily = insights.day_plan_review?.daily ?? [];
  const monthlySummary = insights.monthly_report?.summary ?? {};
  const monthlyFocus = insights.monthly_report?.focus_points ?? [];
  const monthlyMarkdown = insights.monthly_report?.markdown ?? "";
  const llmPromptMarkdown = insights.llm_prompt_markdown ?? "";

  const exportMarkdown = (name: string, content: string) => {
    if (!content) return;
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="grid gap-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Applied Config</h3>
          <pre className="rounded-lg border border-white/10 bg-white/5 p-2 text-xs text-slate-300 whitespace-pre-wrap">{JSON.stringify(appliedConfig, null, 2)}</pre>
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Analysis Scope</h3>
          <SimpleKv kv={analysisScope} />
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Setup Journal</h3>
        <SimpleKv kv={setupQuality} />
        <div className="mt-2">
          <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Setup Label Sources</p>
          <SimpleTable rows={setupSourceRows} />
        </div>
        <div className="mt-2">
          <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Setup Performance</p>
        </div>
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
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Execution Quality</h3>
          <div className="mt-2">
            <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Execution Quality by Entry Hour</p>
            <SimpleTable rows={qualityByEntryHour} />
          </div>
          <div className="mt-3">
            <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Execution Quality by Hold Bucket</p>
            <SimpleTable rows={qualityByHoldBucket} />
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
          {playbookRationale ? (
            <details className="mt-3 rounded-lg border border-white/10 bg-white/5 p-2">
              <summary className="cursor-pointer text-xs uppercase tracking-[0.15em] text-slate-300">Playbook Rationale</summary>
              <div className="mt-2 space-y-3">
                <div>
                  <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Breach Counts</p>
                  <SimpleKv kv={(playbookRationale.breach_counts ?? {}) as Record<string, string | number>} />
                </div>
                <div>
                  <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Worst Entry Hour Signal</p>
                  <SimpleTable rows={playbookRationale.worst_entry_hour ? [playbookRationale.worst_entry_hour] : []} />
                </div>
                <div>
                  <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Worst Hold Bucket Signal</p>
                  <SimpleTable rows={playbookRationale.worst_hold_bucket ? [playbookRationale.worst_hold_bucket] : []} />
                </div>
                <div>
                  <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Best Setup Signal</p>
                  <SimpleTable rows={playbookRationale.best_setup ? [playbookRationale.best_setup] : []} />
                </div>
                <div>
                  <p className="mb-1 text-xs uppercase tracking-[0.15em] text-slate-400">Weak Setup Signal</p>
                  <SimpleTable rows={playbookRationale.weak_setup ? [playbookRationale.weak_setup] : []} />
                </div>
              </div>
            </details>
          ) : null}
        </div>
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">Day Plan Review</h3>
          <SimpleKv kv={dayPlanSummary as Record<string, string | number>} />
          <div className="mt-2">
            <SimpleTable rows={dayPlanDaily.slice(-12)} />
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
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
              <div className="mt-2">
                <button
                  type="button"
                  onClick={() => exportMarkdown("monthly_review_report.md", monthlyMarkdown)}
                  className="rounded border border-white/20 px-2 py-1 text-xs text-slate-200 hover:border-accent hover:text-white"
                >
                  Export MD
                </button>
              </div>
              <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-300">{monthlyMarkdown}</pre>
            </details>
          ) : null}
        </div>
      </div>

      {llmPromptMarkdown ? (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-200">LLM Prompt Pack</h3>
          <div className="mb-2">
            <button
              type="button"
              onClick={() => exportMarkdown("trading_behavior_prompt_pack.md", llmPromptMarkdown)}
              className="rounded border border-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent hover:text-black"
            >
              Export Prompt MD
            </button>
          </div>
          <details className="rounded-lg border border-white/10 bg-white/5 p-2">
            <summary className="cursor-pointer text-xs uppercase tracking-[0.15em] text-slate-300">Preview Prompt</summary>
            <pre className="mt-2 whitespace-pre-wrap text-xs text-slate-300">{llmPromptMarkdown}</pre>
          </details>
        </div>
      ) : null}
    </div>
  );
}

function CheckboxPills({
  options,
  selected,
  onChange,
}: {
  options: string[];
  selected: string[];
  onChange: (next: string[]) => void;
}) {
  if (!options.length) {
    return <p className="text-xs text-slate-500">No options.</p>;
  }
  const toggle = (v: string) => {
    const exists = selected.includes(v);
    onChange(exists ? selected.filter((x) => x !== v) : [...selected, v]);
  };
  return (
    <div className="flex flex-wrap gap-2 rounded-lg border border-white/10 bg-white/5 p-2">
      {options.map((v) => {
        const active = selected.includes(v);
        return (
          <label key={v} className={`inline-flex cursor-pointer items-center gap-2 rounded-full border px-2 py-1 text-xs ${active ? "border-accent bg-accent/20 text-white" : "border-white/15 text-slate-300"}`}>
            <input
              type="checkbox"
              checked={active}
              onChange={() => toggle(v)}
              className="h-3 w-3"
            />
            <span>{v}</span>
          </label>
        );
      })}
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

function AnalysisChart({
  metric,
  points,
  envelopeData,
}: {
  metric: string;
  points: AnalysisSeriesPoint[];
  envelopeData?: { theoretical: AnalysisSeriesPoint[]; actual: AnalysisSeriesPoint[] } | null;
}) {
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

  if (metric === "behavioral_patterns") {
    const days = Array.from(new Set(points.map((p: any) => p.DayOfWeek || "")));
    const hours = Array.from(new Set(points.map((p: any) => p.Hour || 0))).sort((a, b) => a - b);
    const values = points.map((p: any) => Number(p.AvgPnL || 0));
    const maxAbs = Math.max(...values.map((v) => Math.abs(v)), 1);
    const cellMap = new Map<string, { avg: number; trades: number }>();
    (points as any[]).forEach((p) => {
      cellMap.set(`${p.Hour}|${p.DayOfWeek}`, {
        avg: Number(p.AvgPnL || 0),
        trades: Number(p.TradeCount || 0),
      });
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
                const cell = cellMap.get(`${h}|${d}`) || { avg: 0, trades: 0 };
                const intensity = Math.min(Math.abs(cell.avg) / maxAbs, 1);
                const color =
                  cell.avg >= 0 ? `rgba(34,197,94,${0.1 + 0.5 * intensity})` : `rgba(239,68,68,${0.1 + 0.5 * intensity})`;
                return (
                  <div
                    key={`${h}-${d}`}
                    className="flex items-center justify-center text-xs text-white"
                    style={{ backgroundColor: color, minHeight: "32px" }}
                    title={`${d} ${h}:00 | AvgPnL ${cell.avg.toFixed(2)} | Trades ${cell.trades}`}
                  >
                    {cell.avg.toFixed(1)}
                  </div>
                );
              })}
            </React.Fragment>
          ))}
        </div>
      </div>
    );
  }

  if (metric === "performance_envelope" && envelopeData) {
    const theoretical = envelopeData.theoretical ?? [];
    const actual = envelopeData.actual ?? [];
    const theoPts = theoretical.map((p: any) => ({
      x: Number(p.WinningRate ?? 0),
      y: Number(p.TheoreticalWinToLoss ?? 0),
    }));
    const actualPts = actual.map((p: any) => ({
      x: Number(p.WinningRate ?? 0),
      y: Number(p.AvgWinToAvgLoss ?? 0),
    }));
    const data = {
      datasets: [
        {
          label: "Theoretical",
          data: theoPts,
          borderColor: "#94a3b8",
          backgroundColor: "rgba(148,163,184,0.15)",
          pointRadius: 0,
          showLine: true,
          tension: 0.1,
        },
        {
          label: "Actual",
          data: actualPts,
          borderColor: "#22c55e",
          backgroundColor: "rgba(34,197,94,0.35)",
          pointRadius: 4,
          showLine: false,
        },
      ],
    };
    const options = {
      responsive: true,
      plugins: {
        legend: { display: true, labels: { color: "#e2e8f0" } },
      },
      scales: {
        x: {
          type: "linear" as const,
          title: { display: true, text: "Winning Rate (%)", color: "#e2e8f0" },
          ticks: { color: "#e2e8f0" },
          grid: { color: "rgba(226,232,240,0.1)" },
        },
        y: {
          title: { display: true, text: "Win/Loss Ratio", color: "#e2e8f0" },
          ticks: { color: "#e2e8f0" },
          grid: { color: "rgba(226,232,240,0.1)" },
        },
      },
    };
    return <Line data={data} options={options} />;
  }

  if (metric === "pnl_growth") {
    const labels = points.map((p: any) => String(p.Period ?? p.Date ?? ""));
    const strategy = points.map((p: any) => Number(p.CumulativePnL ?? p.NetPnL ?? 0));
    const passive = points.map((p: any) => Number(p.CumulativePassive ?? 0));
    const data = {
      labels,
      datasets: [
        {
          label: "Strategy (CumulativePnL)",
          data: strategy,
          borderColor: "#22c55e",
          backgroundColor: "rgba(34,197,94,0.18)",
          tension: 0.15,
        },
        {
          label: "Passive (CumulativePassive)",
          data: passive,
          borderColor: "#94a3b8",
          backgroundColor: "rgba(148,163,184,0.18)",
          tension: 0.15,
        },
      ],
    };
    const options = {
      responsive: true,
      plugins: {
        legend: { display: true, labels: { color: "#e2e8f0" } },
      },
      scales: {
        x: { ticks: { color: "#e2e8f0" }, grid: { color: "rgba(226,232,240,0.1)" } },
        y: { ticks: { color: "#e2e8f0" }, grid: { color: "rgba(226,232,240,0.1)" } },
      },
    };
    return <Line data={data} options={options} />;
  }

  if (metric === "pnl_distribution") {
    const values = points.map((p: any) => Number(p["PnL(Net)"] ?? 0)).filter((v) => Number.isFinite(v));
    if (!values.length) return <p className="text-slate-400">No data.</p>;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = Math.max(max - min, 1e-9);
    const binCount = Math.min(24, Math.max(8, Math.round(Math.sqrt(values.length))));
    const step = span / binCount;
    const bins = new Array(binCount).fill(0);
    values.forEach((v) => {
      const idx = Math.min(binCount - 1, Math.max(0, Math.floor((v - min) / step)));
      bins[idx] += 1;
    });
    const labels = bins.map((_, i) => {
      const lo = min + i * step;
      const hi = min + (i + 1) * step;
      return `${lo.toFixed(0)}..${hi.toFixed(0)}`;
    });
    const colors = bins.map((_, i) => {
      const center = min + (i + 0.5) * step;
      return center >= 0 ? "rgba(34,197,94,0.65)" : "rgba(239,68,68,0.65)";
    });
    const data = {
      labels,
      datasets: [
        {
          label: "Trade Count",
          data: bins,
          backgroundColor: colors,
          borderColor: colors,
          borderWidth: 1,
        },
      ],
    };
    const options = {
      responsive: true,
      plugins: {
        legend: { display: false },
      },
      scales: {
        x: { ticks: { color: "#e2e8f0", maxRotation: 60, minRotation: 45 }, grid: { color: "rgba(226,232,240,0.08)" } },
        y: { ticks: { color: "#e2e8f0" }, grid: { color: "rgba(226,232,240,0.1)" } },
      },
    };
    return <Bar data={data} options={options} />;
  }

  const labels = points.map((p: any, idx: number) => {
    if (metric === "pnl_distribution") {
      return String(p.TradeIndex ?? idx + 1);
    }
    const raw = p.Period ?? p.TradeDay ?? p.Date ?? p.DateHour ?? p.HourOfDay ?? p.TradeIndex ?? p.HourlyIndex ?? "";
    return String(raw);
  });
  const values = points.map((p: any) => {
    if (metric === "drawdown") return p.Drawdown ?? 0;
    if (metric === "pnl_growth") return p.CumulativePnL ?? p.NetPnL ?? 0;
    if (metric === "pnl_distribution") return p["PnL(Net)"] ?? 0;
    if (metric === "rolling_win_rate") return p.WinRate ?? 0;
    if (metric === "sharpe_ratio") return p.SharpeRatio ?? 0;
    if (metric === "trade_efficiency") return p.Efficiency ?? 0;
    if (metric === "hourly_performance") return p.HourlyPnL ?? 0;
    if (metric === "kelly_criterion") return p.KellyValue ?? 0;
    return 0;
  });

  const data = {
    labels,
    datasets: [
      {
        label: metric,
        data: values,
        borderColor: "#22c55e",
        backgroundColor: "rgba(34,197,94,0.45)",
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

  if (metric === "hourly_performance") {
    return <Bar data={data} options={options} />;
  }
  return <Line data={data} options={options} />;
}

function OvertradingPanel({ daily, trades }: { daily: AnalysisSeriesPoint[]; trades: AnalysisSeriesPoint[] }) {
  const dailyLabels = daily.map((r: any) => String(r.TradeDay ?? ""));
  const dailyTrades = daily.map((r: any) => Number(r.TradesPerDay ?? 0));
  const dailyPnl = daily.map((r: any) => Number(r.DailyPnL ?? 0));
  const dailyData = {
    labels: dailyLabels,
    datasets: [
      {
        type: "bar" as const,
        label: "Trades/Day",
        yAxisID: "yTrades",
        data: dailyTrades,
        backgroundColor: "rgba(96,165,250,0.5)",
        borderColor: "rgba(96,165,250,0.9)",
      },
      {
        type: "line" as const,
        label: "Daily PnL",
        yAxisID: "yPnl",
        data: dailyPnl,
        borderColor: "#22c55e",
        backgroundColor: "rgba(34,197,94,0.2)",
        tension: 0.2,
      },
    ],
  };
  const dailyOptions = {
    responsive: true,
    plugins: { legend: { display: true, labels: { color: "#e2e8f0" } } },
    scales: {
      x: { ticks: { color: "#e2e8f0", maxRotation: 60, minRotation: 45 }, grid: { color: "rgba(226,232,240,0.08)" } },
      yTrades: {
        type: "linear" as const,
        position: "left" as const,
        ticks: { color: "#93c5fd" },
        grid: { color: "rgba(226,232,240,0.08)" },
      },
      yPnl: {
        type: "linear" as const,
        position: "right" as const,
        ticks: { color: "#86efac" },
        grid: { drawOnChartArea: false },
      },
    },
  };

  const scatterData = {
    datasets: [
      {
        label: "R-multiple by trade",
        data: trades.map((r: any) => ({
          x: Number(r.TradeIndex ?? 0),
          y: Number(r.R_multiple ?? 0),
        })),
        pointRadius: 4,
        showLine: false,
        backgroundColor: trades.map((r: any) => {
          const tag = String(r.TradeTag ?? "");
          if (tag === "DarkRed") return "rgba(127,29,29,0.95)";
          if (tag === "LightCoral") return "rgba(248,113,113,0.9)";
          return "rgba(96,165,250,0.8)";
        }),
        borderColor: trades.map((r: any) => {
          const tag = String(r.TradeTag ?? "");
          if (tag === "DarkRed") return "rgba(127,29,29,1)";
          if (tag === "LightCoral") return "rgba(248,113,113,1)";
          return "rgba(96,165,250,1)";
        }),
      },
    ],
  };
  const scatterOptions = {
    responsive: true,
    plugins: { legend: { display: true, labels: { color: "#e2e8f0" } } },
    scales: {
      x: { title: { display: true, text: "TradeIndex", color: "#e2e8f0" }, ticks: { color: "#e2e8f0" }, grid: { color: "rgba(226,232,240,0.08)" } },
      y: { title: { display: true, text: "R-multiple", color: "#e2e8f0" }, ticks: { color: "#e2e8f0" }, grid: { color: "rgba(226,232,240,0.1)" } },
    },
  };

  return (
    <div className="grid gap-4">
      <div>
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Daily Overtrading View</h3>
        <Chart type="bar" data={dailyData} options={dailyOptions} />
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-slate-200">Trade-Level Risk Scatter</h3>
        <Scatter data={scatterData} options={scatterOptions} />
      </div>
    </div>
  );
}
