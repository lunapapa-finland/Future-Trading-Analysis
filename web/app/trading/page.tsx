"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { CandlesChart } from "@/components/charts/candles-chart";
import { SymbolSelect } from "@/components/forms/symbol-select";
import { TimeframeSelect } from "@/components/forms/timeframe-select";
import { getDayPlan, getDayPlanTaxonomy, getTagTaxonomy, getTradingSession, postDayPlan, postJournalSetupTags } from "@/lib/api";
import { resampleCandles } from "@/lib/timeframes";
import { Candle, Timeframe, TradeMarker } from "@/lib/types";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { StatGrid } from "@/components/ui/stat-grid";
import dynamic from "next/dynamic";
const PlaybackControls = dynamic(() => import("@/components/ui/playback-controls").then((m) => m.PlaybackControls), { ssr: false });
type PlaybackState = import("@/components/ui/playback-controls").PlaybackState;

export default function TradingPage() {
  const [symbol, setSymbol] = useState("MES");
  const [timeframe, setTimeframe] = useState<Timeframe>("5m");
  const [showTrades, setShowTrades] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showVwap, setShowVwap] = useState(false);
  const [showEma, setShowEma] = useState(false);
  const [showBarCount, setShowBarCount] = useState(false);
  const [directionFilter, setDirectionFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [sizeFilter, setSizeFilter] = useState("");
  const [playbackSlice, setPlaybackSlice] = useState<Candle[]>([]);
  const [playbackIndex, setPlaybackIndex] = useState(0);
  const [tagDrafts, setTagDrafts] = useState<Record<string, { Phase: string; Context: string; Setup: string; SignalBar: string; TradeIntent: string }>>({});
  const [setupSaving, setSetupSaving] = useState(false);
  const [setupMessage, setSetupMessage] = useState<string>("");
  const today = new Date().toISOString().slice(0, 10);
  const [planDate, setPlanDate] = useState(today);
  const [planBias, setPlanBias] = useState("");
  const [planDayType, setPlanDayType] = useState("");
  const [actualDayType, setActualDayType] = useState("");
  const [planLevels, setPlanLevels] = useState("");
  const [planPrimary, setPlanPrimary] = useState("");
  const [planAvoidance, setPlanAvoidance] = useState("");
  const [planSaving, setPlanSaving] = useState(false);
  const [planMessage, setPlanMessage] = useState<string>("");
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);

  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["session", symbol, startDate, endDate],
    queryFn: () => getTradingSession({ symbol, start: startDate, end: endDate }),
    staleTime: 30_000,
    refetchOnWindowFocus: false
  });
  const { data: taxonomy } = useQuery({
    queryKey: ["tag-taxonomy"],
    queryFn: () => getTagTaxonomy(),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  const { data: dayPlanTaxonomy } = useQuery({
    queryKey: ["day-plan-taxonomy"],
    queryFn: () => getDayPlanTaxonomy(),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  const { data: dayPlanRange, refetch: refetchDayPlan } = useQuery({
    queryKey: ["day-plan-range", startDate, endDate],
    queryFn: () => getDayPlan({ start: startDate, end: endDate }),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  const phaseOptions = useMemo(() => (taxonomy?.phase ?? []).map((x) => x.value), [taxonomy?.phase]);
  const contextOptions = useMemo(() => (taxonomy?.context ?? []).map((x) => x.value), [taxonomy?.context]);
  const setupOptions = useMemo(() => (taxonomy?.setup ?? []).map((x) => x.value), [taxonomy?.setup]);
  const signalOptions = useMemo(() => (taxonomy?.signal_bar ?? []).map((x) => x.value), [taxonomy?.signal_bar]);
  const tradeIntentOptions = useMemo(() => {
    const opts = (taxonomy?.trade_intent ?? []).map((x) => x.value);
    return opts.length ? opts : ["Scalp", "Swing", "Runner", "Scale-in", "Scale-out"];
  }, [taxonomy?.trade_intent]);
  const dayBiasOptions = useMemo(() => {
    const opts = (dayPlanTaxonomy?.bias ?? []).map((x) => x.value);
    return opts.length ? opts : ["Bullish", "Bearish", "Neutral"];
  }, [dayPlanTaxonomy?.bias]);
  const dayTypeOptions = useMemo(() => {
    const opts = (dayPlanTaxonomy?.expected_day_type ?? []).map((x) => x.value);
    return opts.length ? opts : ["Trend day", "TR day", "Trend from open", "Spike and channel", "Double distribution"];
  }, [dayPlanTaxonomy?.expected_day_type]);
  const dayPlanByDate = useMemo(() => {
    const out = new Map<string, Record<string, unknown>>();
    (dayPlanRange?.rows ?? []).forEach((r) => {
      const day = String(r["Date"] || "").trim();
      if (day) out.set(day, r);
    });
    return out;
  }, [dayPlanRange?.rows]);
  const businessDayOptions = useMemo(() => {
    const out: string[] = [];
    if (!startDate || !endDate) return out;
    const start = new Date(`${startDate}T00:00:00`);
    const end = new Date(`${endDate}T00:00:00`);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return out;
    const cur = new Date(start);
    while (cur <= end) {
      const wd = cur.getDay();
      if (wd !== 0 && wd !== 6) {
        out.push(cur.toISOString().slice(0, 10));
      }
      cur.setDate(cur.getDate() + 1);
    }
    return out;
  }, [startDate, endDate]);

  const viewData = useMemo(() => {
    const source = data?.future ?? [];
    return resampleCandles(source, timeframe);
  }, [data, timeframe]);

  const lastBar: Candle | undefined = viewData[viewData.length - 1];
  const tradeMarkers: TradeMarker[] = useMemo(
    () =>
      data?.performance?.map((p) => ({
        entryTime: String(p["EnteredAt"] || p["TradeDay"] || ""),
        exitTime: String(p["ExitedAt"] || p["TradeDay"] || ""),
        entryPrice: Number(p["EntryPrice"] || p["Entry"] || p["Open"] || 0),
        exitPrice: Number(p["ExitPrice"] || p["Exit"] || p["Close"] || 0),
        pnl: Number(p["PnL(Net)"] || 0),
        type: String(p["Type"] || ""),
        size: Number(p["Size"] || 0)
      })) || [],
    [data?.performance]
  );

  const durationBins = useMemo(() => {
    const bins = { scalp: 0, hybrid: 0, swing: 0 };
    (data?.performance || []).forEach((p) => {
      const enter = new Date(String(p["EnteredAt"] || "")).getTime();
      const exit = new Date(String(p["ExitedAt"] || "")).getTime();
      if (Number.isNaN(enter) || Number.isNaN(exit)) return;
      const mins = (exit - enter) / 60000;
      if (mins <= 5) bins.scalp += 1;
      else if (mins < 30) bins.hybrid += 1;
      else bins.swing += 1;
    });
    return [
      { label: "Scalp (<=5m)", count: bins.scalp },
      { label: "Scalp/Swing (5-30m)", count: bins.hybrid },
      { label: "Swing (>=30m)", count: bins.swing }
    ];
  }, [data?.performance]);

  const computeStudyLines = useMemo(
    () =>
      (source: Candle[]) => {
        const points = source.map((b) => ({
          ts: new Date(b.time).getTime(),
          close: b.close,
          high: b.high,
          low: b.low,
          vol: b.volume ?? 0
        }));

        const lines: { id: string; color: string; points: { timestamp: number; value: number }[] }[] = [];

        if (showEma && points.length) {
          const period = 20;
          let ema = points[0].close;
          const alpha = 2 / (period + 1);
          const emaPts: { timestamp: number; value: number }[] = [];
          points.forEach((p, idx) => {
            if (idx === 0) {
              ema = p.close;
            } else {
              ema = p.close * alpha + ema * (1 - alpha);
            }
            if (idx >= period - 1) {
              emaPts.push({ timestamp: p.ts, value: ema });
            }
          });
          if (emaPts.length > 1) lines.push({ id: "ema20", color: "#6366f1", points: emaPts });
        }

        if (showVwap && points.length) {
          let cumPv = 0;
          let cumVol = 0;
          const vwapPts: { timestamp: number; value: number }[] = [];
          points.forEach((p) => {
            const v = p.vol || 1;
            const typical = (p.high + p.low + p.close) / 3;
            cumPv += typical * v;
            cumVol += v;
            if (cumVol > 0) {
              vwapPts.push({ timestamp: p.ts, value: cumPv / cumVol });
            }
          });
          if (vwapPts.length > 1) lines.push({ id: "vwap", color: "#f59e0b", points: vwapPts });
        }

        if (showBarCount && points.length) {
          const bars = points.map((p, idx) => {
            const cushion = Math.max(p.high - p.low, 0.0001) * 0.02;
            const price = p.low - cushion;
            return {
              timestamp: p.ts,
              value: price,
              label: idx + 1
            };
          });
          lines.push({ id: "barcount", color: "#334155", points: bars });
        }

        return lines;
      },
    [showEma, showVwap, showBarCount]
  );

  const studyLines = useMemo(() => computeStudyLines(viewData), [computeStudyLines, viewData]);

  const fullscreenData = playbackSlice.length ? playbackSlice : viewData;
  const fullscreenStudyLines = useMemo(
    () => computeStudyLines(fullscreenData),
    [computeStudyLines, fullscreenData]
  );

  const fullscreenTrades = useMemo(() => {
    if (!fullscreenData.length) return tradeMarkers;
    const minTs = new Date(fullscreenData[0].time).getTime();
    const maxTs = new Date(fullscreenData[fullscreenData.length - 1].time).getTime();
    return tradeMarkers.filter((t) => {
      const entry = new Date(t.entryTime).getTime();
      const exit = new Date(t.exitTime).getTime();
      if (Number.isNaN(entry) && Number.isNaN(exit)) return false;
      const earliest = Number.isNaN(entry) ? exit : Number.isNaN(exit) ? entry : Math.min(entry, exit);
      const latest = Number.isNaN(entry) ? exit : Number.isNaN(exit) ? entry : Math.max(entry, exit);
      return latest >= minTs && earliest <= maxTs;
    });
  }, [fullscreenData, tradeMarkers]);

  const ohlcRange = useMemo(() => {
    if (!viewData.length) return null;
    const open = viewData[0].open;
    const close = viewData[viewData.length - 1].close;
    const high = Math.max(...viewData.map((b) => b.high));
    const low = Math.min(...viewData.map((b) => b.low));
    return { open, high, low, close };
  }, [viewData]);

  const makeTradeKey = (row: Record<string, unknown>) => {
    const tid = String(row["trade_id"] || "").trim();
    if (tid) return `tid:${tid}`;
    return [
      String(row["TradeDay"] || "").trim(),
      String(row["ContractName"] || "").trim(),
      String(row["IntradayIndex"] || "").trim()
    ].join("|");
  };

  const normalizeSetupString = (v: string) => {
    const vals = v
      .replace(/;/g, "|")
      .replace(/,/g, "|")
      .split("|")
      .map((s) => s.trim())
      .filter(Boolean);
    const out: string[] = [];
    const seen = new Set<string>();
    vals.forEach((s) => {
      const k = s.toLowerCase();
      if (seen.has(k)) return;
      seen.add(k);
      out.push(s);
    });
    return out.join(" | ");
  };
  const splitSetupValues = (v: string) => normalizeSetupString(v).split("|").map((s) => s.trim()).filter(Boolean);
  const toggleSetupChoice = (row: Record<string, unknown>, option: string) => {
    const current = splitSetupValues(getDraft(row).Setup);
    const has = current.some((x) => x.toLowerCase() === option.toLowerCase());
    const next = has ? current.filter((x) => x.toLowerCase() !== option.toLowerCase()) : [...current, option];
    setDraftField(row, "Setup", next.join(" | "));
  };

  const getDraft = (row: Record<string, unknown>) => {
    const key = makeTradeKey(row);
    const existing = tagDrafts[key];
    if (existing) return existing;
    return {
      Phase: String(row["Phase"] || ""),
      Context: String(row["Context"] || ""),
      Setup: String(row["Setup"] || ""),
      SignalBar: String(row["SignalBar"] || ""),
      TradeIntent: String(row["TradeIntent"] || ""),
    };
  };

  const setDraftField = (row: Record<string, unknown>, field: "Phase" | "Context" | "Setup" | "SignalBar" | "TradeIntent", value: string) => {
    const key = makeTradeKey(row);
    setTagDrafts((prev) => ({
      ...prev,
      [key]: {
        ...getDraft(row),
        ...(prev[key] || {}),
        [field]: value,
      },
    }));
  };

  const saveSetupTags = async () => {
    const rows = (data?.performance || []) as Record<string, unknown>[];
    const changed = rows
      .map((row) => {
        const key = makeTradeKey(row);
        const draft = tagDrafts[key];
        if (draft == null) return null;
        const currentSetup = normalizeSetupString(String(row["Setup"] || ""));
        const currentPhase = String(row["Phase"] || "").trim();
        const currentContext = String(row["Context"] || "").trim();
        const currentSignal = String(row["SignalBar"] || "").trim();
        const currentIntent = String(row["TradeIntent"] || "").trim();
        const nextSetup = normalizeSetupString(draft.Setup || "");
        const nextPhase = String(draft.Phase || "").trim();
        const nextContext = String(draft.Context || "").trim();
        const nextSignal = String(draft.SignalBar || "").trim();
        const nextIntent = String(draft.TradeIntent || "").trim();
        if (
          nextSetup === currentSetup &&
          nextPhase === currentPhase &&
          nextContext === currentContext &&
          nextSignal === currentSignal &&
          nextIntent === currentIntent
        ) {
          return null;
        }
        return {
          trade_id: String(row["trade_id"] || "").trim() || undefined,
          TradeDay: String(row["TradeDay"] || "").trim() || undefined,
          ContractName: String(row["ContractName"] || "").trim() || undefined,
          IntradayIndex: String(row["IntradayIndex"] || "").trim() || undefined,
          Phase: nextPhase,
          Context: nextContext,
          SignalBar: nextSignal,
          TradeIntent: nextIntent,
          setups: nextSetup,
        };
      })
      .filter(Boolean) as Array<{
        trade_id?: string;
        TradeDay?: string;
        ContractName?: string;
        IntradayIndex?: string;
        Phase?: string;
        Context?: string;
        SignalBar?: string;
        TradeIntent?: string;
        setups: string;
      }>;
    if (!changed.length) {
      setSetupMessage("No tag changes to save.");
      return;
    }
    try {
      setSetupSaving(true);
      setSetupMessage("");
      const resp = await postJournalSetupTags({ rows: changed });
      setTagDrafts({});
      setSetupMessage(`Saved setup tags: updated ${resp.updated}, inserted ${resp.inserted}.`);
      await refetch();
    } catch (e) {
      setSetupMessage(`Failed to save tags: ${(e as Error).message}`);
    } finally {
      setSetupSaving(false);
    }
  };


  useEffect(() => {
    // Reset toggles when timeframe changes
    setShowTrades(false);
    setShowVwap(false);
    setShowEma(false);
    setShowBarCount(false);
    setDirectionFilter("");
    setTypeFilter("");
    setSizeFilter("");
  }, [timeframe]);

  useEffect(() => {
    if (!businessDayOptions.length) {
      setPlanDate("");
      return;
    }
    if (!planDate || !businessDayOptions.includes(planDate)) {
      setPlanDate(businessDayOptions[0]);
    }
  }, [businessDayOptions, planDate]);

  useEffect(() => {
    const row = dayPlanByDate.get(planDate);
    if (!row) {
      setPlanBias("");
      setPlanDayType("");
      setActualDayType("");
      setPlanLevels("");
      setPlanPrimary("");
      setPlanAvoidance("");
      return;
    }
    setPlanBias(String(row["Bias"] || ""));
    setPlanDayType(String(row["ExpectedDayType"] || ""));
    setActualDayType(String(row["ActualDayType"] || ""));
    setPlanLevels(String(row["KeyLevelsHTFContext"] || ""));
    setPlanPrimary(String(row["PrimaryPlan"] || ""));
    setPlanAvoidance(String(row["AvoidancePlan"] || ""));
  }, [planDate, dayPlanByDate]);

  const saveDayPlan = async () => {
    if (!planDate) {
      setPlanMessage("No business day available in the selected range.");
      return;
    }
    try {
      setPlanSaving(true);
      setPlanMessage("");
      const resp = await postDayPlan({
        rows: [
          {
            Date: planDate,
            Bias: planBias,
            ExpectedDayType: planDayType,
            ActualDayType: actualDayType,
            KeyLevelsHTFContext: planLevels,
            PrimaryPlan: planPrimary,
            AvoidancePlan: planAvoidance,
          },
        ],
      });
      setPlanMessage(`Saved day plan: updated ${resp.updated}, inserted ${resp.inserted}.`);
      await refetchDayPlan();
    } catch (e) {
      setPlanMessage(`Failed to save day plan: ${(e as Error).message}`);
    } finally {
      setPlanSaving(false);
    }
  };

  return (
    <AppShell active="/trading">
      <div className="grid gap-4 xl:grid-cols-[1fr_300px]">
        <Card title="Controls">
          <div className="space-y-3">
            <div className="rounded-xl border border-white/10 bg-surface/80 p-3">
              <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
                <SymbolSelect value={symbol} onChange={setSymbol} />
                <TimeframeSelect value={timeframe} onChange={setTimeframe} />
                {[
                  { label: "Today", anchor: "today" },
                  { label: "This Week", anchor: "week" },
                  { label: "This Month", anchor: "month" }
                ].map((preset) => (
                  <button
                    key={preset.label}
                    className="h-[38px] rounded-lg border border-white/10 px-3 text-sm font-semibold text-slate-200 transition hover:border-accent/60 sm:w-auto"
                    onClick={() => {
                      const now = new Date();
                      const start = new Date(now);
                      if (preset.anchor === "week") {
                        const day = now.getDay() === 0 ? 7 : now.getDay();
                        start.setDate(now.getDate() - (day - 1));
                      } else if (preset.anchor === "month") {
                        start.setDate(1);
                      }
                      const startIso = start.toISOString().slice(0, 10);
                      const endIso = now.toISOString().slice(0, 10);
                      setStartDate(startIso);
                      setEndDate(endIso);
                    }}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-surface/80 p-3 space-y-3">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-sm text-slate-300">
                  Start
                  <input
                    type="date"
                    value={startDate}
                    max={endDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="h-[38px] rounded-lg border border-white/10 bg-surface px-3 text-white outline-none focus:border-accent"
                  />
                </label>
                <label className="flex flex-col gap-1 text-sm text-slate-300">
                  End
                  <input
                    type="date"
                    value={endDate}
                    min={startDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="h-[38px] rounded-lg border border-white/10 bg-surface px-3 text-white outline-none focus:border-accent"
                  />
                </label>
              </div>
            </div>

            <div className="rounded-xl border border-white/10 bg-surface/80 p-3 space-y-3">
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {[
                  { label: showTrades ? "Hide Trades" : "Show Trades", active: showTrades, onClick: () => setShowTrades((s) => !s) },
                  { label: "EMA 20", active: showEma, onClick: () => setShowEma((v) => !v) },
                  { label: "VWAP", active: showVwap, onClick: () => setShowVwap((v) => !v) },
                  { label: "Bar Count", active: showBarCount, onClick: () => setShowBarCount((v) => !v) }
                ].map((btn) => (
                  <button
                    key={btn.label}
                    className={`h-[38px] rounded-lg px-3 text-sm font-semibold transition ${
                      btn.active
                        ? "border border-accent/50 bg-accent/25 text-white"
                        : "border border-white/10 bg-white/5 text-slate-200 hover:border-accent/40"
                    }`}
                    onClick={btn.onClick}
                  >
                    {btn.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </Card>
        <Card title="Market Snapshot">
          {lastBar && ohlcRange ? (
            <div className="grid grid-cols-1 gap-2 text-sm text-slate-200 sm:grid-cols-2">
              <span className="text-slate-400">Range</span>
              <span className="text-right text-white">{startDate} → {endDate}</span>
              <span className="text-slate-400">Open</span>
              <span className="text-right font-semibold text-white">{ohlcRange.open.toFixed(4)}</span>
              <span className="text-slate-400">High</span>
              <span className="text-right">{ohlcRange.high.toFixed(4)}</span>
              <span className="text-slate-400">Low</span>
              <span className="text-right">{ohlcRange.low.toFixed(4)}</span>
              <span className="text-slate-400">Close</span>
              <span className="text-right font-semibold text-white">{ohlcRange.close.toFixed(4)}</span>
            </div>
          ) : (
            <p className="text-slate-400">No data yet.</p>
          )}
        </Card>
      </div>

      <Card title="Price Action" className="mt-2">
        {error ? (
          <p className="text-sm text-red-300">Failed to load candles: {(error as Error).message}</p>
        ) : (
          <div className="flex flex-col gap-3">
            {isFetching && <p className="text-xs uppercase tracking-[0.2em] text-slate-400">Loading…</p>}
            <CandlesChart
              data={viewData}
              trades={tradeMarkers}
              showTrades={showTrades}
              heightClass={isFullscreen ? "h-[70vh]" : "h-[420px]"}
              studyLines={studyLines}
            />
            <div className="flex justify-end">
              <button
                className="rounded-lg border border-white/10 px-4 py-2 text-sm font-semibold text-slate-100 transition hover:border-highlight"
                onClick={() => setIsFullscreen((v) => !v)}
              >
                {isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
              </button>
            </div>
            <p className="text-xs text-slate-400">
              Rendering {viewData.length} bars ({timeframe}) from 5m raw feed. Range: {startDate} → {endDate}
            </p>
          </div>
        )}
      </Card>

      {isFullscreen && (
        <div className="fixed inset-0 z-50 overflow-auto bg-black/80 p-2 sm:p-4">
          <div className="mx-auto flex max-w-6xl flex-col gap-3 rounded-2xl border border-white/10 bg-surface/90 p-3 shadow-2xl sm:p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-accent">Price Action</p>
                <p className="text-sm font-semibold text-white sm:text-lg">
                  {symbol} — {startDate} → {endDate}
                </p>
              </div>
              <button
                className="rounded-full border border-white/20 px-3 py-1 text-xs font-semibold text-slate-200 hover:border-accent"
                onClick={() => setIsFullscreen(false)}
              >
                Close
              </button>
            </div>
            <PlaybackControls
              maxIndex={Math.max(viewData.length - 1, 0)}
              speeds={undefined}
              onChange={({ index }: PlaybackState) => {
                setPlaybackIndex(index);
                const slice = viewData.slice(0, index + 1);
                setPlaybackSlice(slice);
              }}
            />
            <CandlesChart
              data={fullscreenData}
              trades={fullscreenTrades}
              showTrades={showTrades}
              heightClass="h-[70vh] sm:h-[80vh]"
              studyLines={fullscreenStudyLines}
            />
          </div>
        </div>
      )}

      <Card title="Trades Stats" className="mt-2">
        {data ? (
          <div className="space-y-4">
            <StatGrid stats={{ ...(data.stats || {}), duration_bins: durationBins }} />
            <div className="rounded-lg border border-white/5 bg-white/5 p-3 space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs uppercase tracking-[0.15em] text-slate-300">Daily Plan (Day-Level Journal)</p>
                <span className="text-[11px] text-slate-400">Range-bound to {startDate} → {endDate}</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {(dayPlanRange?.rows ?? []).length ? (
                  (dayPlanRange?.rows ?? []).map((r) => {
                    const d = String((r as Record<string, unknown>)["Date"] || "");
                    return (
                      <button
                        key={d}
                        type="button"
                        onClick={() => setPlanDate(d)}
                        className={`rounded border px-2 py-0.5 text-[11px] ${planDate === d ? "border-accent text-white" : "border-white/15 text-slate-300"}`}
                      >
                        {d}
                      </button>
                    );
                  })
                ) : (
                  <span className="text-[11px] text-slate-400">No day-plan rows in selected range.</span>
                )}
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs text-slate-300">
                  Date
                  <select
                    value={planDate}
                    onChange={(e) => setPlanDate(e.target.value)}
                    disabled={!businessDayOptions.length}
                    className="h-[32px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                  >
                    {!businessDayOptions.length ? <option value="">No business days</option> : null}
                    {businessDayOptions.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-300">
                  Bias
                  <select
                    value={planBias}
                    onChange={(e) => setPlanBias(e.target.value)}
                    className="h-[32px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                  >
                    <option value="">Select</option>
                    {dayBiasOptions.map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-300">
                  Expected Day Type
                  <select
                    value={planDayType}
                    onChange={(e) => setPlanDayType(e.target.value)}
                    className="h-[32px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                  >
                    <option value="">Select</option>
                    {dayTypeOptions.map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-300">
                  Actual Day Type
                  <select
                    value={actualDayType}
                    onChange={(e) => setActualDayType(e.target.value)}
                    className="h-[32px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                  >
                    <option value="">Select</option>
                    {dayTypeOptions.map((v) => (
                      <option key={v} value={v}>{v}</option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-300 sm:col-span-2">
                  Key Levels / HTF Context
                  <textarea
                    value={planLevels}
                    onChange={(e) => setPlanLevels(e.target.value)}
                    rows={2}
                    className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs text-white outline-none focus:border-accent"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-300 sm:col-span-2">
                  Primary Plan
                  <textarea
                    value={planPrimary}
                    onChange={(e) => setPlanPrimary(e.target.value)}
                    rows={2}
                    className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs text-white outline-none focus:border-accent"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-300 sm:col-span-2">
                  Avoidance Plan
                  <textarea
                    value={planAvoidance}
                    onChange={(e) => setPlanAvoidance(e.target.value)}
                    rows={2}
                    className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs text-white outline-none focus:border-accent"
                  />
                </label>
              </div>
              <div className="flex items-center justify-between gap-2">
                <button
                  type="button"
                  onClick={saveDayPlan}
                  disabled={planSaving || !planDate}
                  className="rounded border border-accent px-3 py-1 text-xs font-semibold text-white hover:bg-accent hover:text-black disabled:opacity-60"
                >
                  {planSaving ? "Saving..." : "Save Day Plan"}
                </button>
                {planMessage ? <span className="text-xs text-slate-300">{planMessage}</span> : null}
              </div>
            </div>
              <div className="space-y-2 rounded-lg border border-white/5 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">
                <span>Tag each trade with Phase, Context, Setup(s), Signal Bar, and Trade Intent. Use `|` or `,` for multiple setups.</span>
                <button
                  type="button"
                  onClick={saveSetupTags}
                  disabled={setupSaving}
                  className="rounded border border-accent px-3 py-1 font-semibold text-white hover:bg-accent hover:text-black disabled:opacity-60"
                >
                  {setupSaving ? "Saving..." : "Save Setup Tags"}
                </button>
              </div>
              {setupMessage ? <p className="text-xs text-slate-300">{setupMessage}</p> : null}
              <div className="grid gap-2 text-sm text-slate-200 sm:flex sm:flex-wrap sm:gap-3">
                <label className="flex items-center justify-between gap-2 sm:justify-start">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Direction</span>
                  <select
                    className="h-[38px] min-w-[130px] rounded-lg border border-white/10 bg-surface px-3 text-sm text-white outline-none focus:border-accent"
                    value={directionFilter}
                    onChange={(e) => setDirectionFilter(e.target.value)}
                  >
                    <option value="">All</option>
                    <option value="Long">Long</option>
                    <option value="Short">Short</option>
                  </select>
                </label>
                <label className="flex items-center justify-between gap-2 sm:justify-start">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Type</span>
                  <select
                    className="h-[38px] min-w-[130px] rounded-lg border border-white/10 bg-surface px-3 text-sm text-white outline-none focus:border-accent"
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                  >
                    <option value="">All</option>
                    <option value="Scalp">Scalp</option>
                    <option value="Scalp/Swing">Scalp/Swing</option>
                    <option value="Swing">Swing</option>
                  </select>
                </label>
                <label className="flex items-center justify-between gap-2 sm:justify-start">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Size</span>
                  <select
                    className="h-[38px] min-w-[130px] rounded-lg border border-white/10 bg-surface px-3 text-sm text-white outline-none focus:border-accent"
                    value={sizeFilter}
                    onChange={(e) => setSizeFilter(e.target.value)}
                  >
                    <option value="">All</option>
                    <option value="S">Small (&lt;=2)</option>
                    <option value="M">Medium (&lt;=5)</option>
                    <option value="L">Large (&gt;5)</option>
                  </select>
                </label>
              </div>
              <div className="space-y-2 md:hidden">
                {(data.performance || []).map((row, idx) => {
                  const enter = new Date(String(row["EnteredAt"] || "")).getTime();
                  const exit = new Date(String(row["ExitedAt"] || "")).getTime();
                  const mins = !Number.isNaN(enter) && !Number.isNaN(exit) ? (exit - enter) / 60000 : null;
                  const holdType =
                    mins == null ? "N/A" : mins <= 5 ? "Scalp" : mins < 30 ? "Scalp/Swing" : "Swing";
                  const direction = String(row["Type"] || "");
                  const sizeVal = Number(row["Size"] || 0);
                  const draft = getDraft(row as Record<string, unknown>);

                  const dirOk = !directionFilter || direction === directionFilter;
                  const typeOk = !typeFilter || holdType === typeFilter;
                  const sizeOk =
                    !sizeFilter ||
                    (sizeFilter === "S" && sizeVal <= 2) ||
                    (sizeFilter === "M" && sizeVal > 2 && sizeVal <= 5) ||
                    (sizeFilter === "L" && sizeVal > 5);
                  if (!dirOk || !typeOk || !sizeOk) return null;
                  return (
                    <div key={idx} className="rounded-lg border border-white/10 bg-white/5 p-2 text-xs text-slate-200">
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">#</span><span>{idx + 1}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Entry</span><span className="break-words">{String(row["EnteredAt"] || row["TradeDay"] || "")}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Exit</span><span className="break-words">{String(row["ExitedAt"] || "")}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">PnL(Net)</span><span className="text-emerald-300">{Number(row["PnL(Net)"] || 0).toFixed(4)}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Size</span><span>{sizeVal}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Direction</span><span>{direction}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Type</span><span>{holdType}</span></div>
                      <div className="rounded border border-white/10 bg-white/5 p-2">
                        <p className="mb-1 text-[10px] uppercase tracking-[0.15em] text-slate-400">Tags</p>
                        <div className="grid grid-cols-2 gap-2">
                          <select
                            value={draft.Phase}
                            onChange={(e) => setDraftField(row as Record<string, unknown>, "Phase", e.target.value)}
                            className="h-[30px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                          >
                            <option value="">Phase</option>
                            {phaseOptions.map((v) => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                          <select
                            value={draft.Context}
                            onChange={(e) => setDraftField(row as Record<string, unknown>, "Context", e.target.value)}
                            className="h-[30px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                          >
                            <option value="">Context</option>
                            {contextOptions.map((v) => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                          <select
                            value={draft.SignalBar}
                            onChange={(e) => setDraftField(row as Record<string, unknown>, "SignalBar", e.target.value)}
                            className="h-[30px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                          >
                            <option value="">SignalBar</option>
                            {signalOptions.map((v) => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                          <select
                            value={draft.TradeIntent}
                            onChange={(e) => setDraftField(row as Record<string, unknown>, "TradeIntent", e.target.value)}
                            className="h-[30px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                          >
                            <option value="">TradeIntent</option>
                            {tradeIntentOptions.map((v) => (
                              <option key={v} value={v}>{v}</option>
                            ))}
                          </select>
                          <input
                            type="text"
                            value={draft.Setup}
                            list="setup-options"
                            onChange={(e) => setDraftField(row as Record<string, unknown>, "Setup", e.target.value)}
                            placeholder="Setup(s): Wedge | BO + Follow-through"
                            className="h-[30px] w-full rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                          />
                        </div>
                        <details className="mt-1 rounded border border-white/10 bg-white/5 px-2 py-1">
                          <summary className="cursor-pointer text-[11px] text-slate-300">Pick Setup Tags</summary>
                          <div className="mt-1 grid grid-cols-1 gap-1">
                            {setupOptions.map((opt) => {
                              const checked = splitSetupValues(draft.Setup).some((v) => v.toLowerCase() === opt.toLowerCase());
                              return (
                                <label key={opt} className="inline-flex items-center gap-2 text-[11px] text-slate-200">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    onChange={() => toggleSetupChoice(row as Record<string, unknown>, opt)}
                                  />
                                  <span>{opt}</span>
                                </label>
                              );
                            })}
                          </div>
                        </details>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="hidden md:block">
                <table className="w-full table-fixed divide-y divide-white/5 text-sm text-slate-200">
                  <colgroup>
                    <col className="w-[40px]" />
                    <col className="w-[140px]" />
                    <col className="w-[140px]" />
                    <col className="w-[96px]" />
                    <col className="w-[64px]" />
                    <col className="w-[88px]" />
                    <col className="w-[100px]" />
                    <col />
                  </colgroup>
                  <thead className="bg-white/5 text-xs uppercase tracking-wide text-slate-400">
                    <tr>
                      <th className="px-1 py-1 text-left">#</th>
                      <th className="px-1 py-1 text-left">Entry</th>
                      <th className="px-1 py-1 text-left">Exit</th>
                      <th className="px-1 py-1 text-right">PnL(Net)</th>
                      <th className="px-1 py-1 text-right">Size</th>
                      <th className="px-1 py-1 text-left">Direction</th>
                      <th className="px-1 py-1 text-left">Type</th>
                      <th className="px-1 py-1 text-left">Tags</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {(data.performance || []).map((row, idx) => {
                      const enter = new Date(String(row["EnteredAt"] || "")).getTime();
                      const exit = new Date(String(row["ExitedAt"] || "")).getTime();
                      const mins = !Number.isNaN(enter) && !Number.isNaN(exit) ? (exit - enter) / 60000 : null;
                      const holdType =
                        mins == null
                          ? "N/A"
                          : mins <= 5
                            ? "Scalp"
                            : mins < 30
                              ? "Scalp/Swing"
                              : "Swing";
                      const direction = String(row["Type"] || "");
                      const sizeVal = Number(row["Size"] || 0);
                      const draft = getDraft(row as Record<string, unknown>);

                      const dirOk = !directionFilter || direction === directionFilter;
                      const typeOk = !typeFilter || holdType === typeFilter;
                      const sizeOk =
                        !sizeFilter ||
                        (sizeFilter === "S" && sizeVal <= 2) ||
                        (sizeFilter === "M" && sizeVal > 2 && sizeVal <= 5) ||
                        (sizeFilter === "L" && sizeVal > 5);
                      if (!dirOk || !typeOk || !sizeOk) return null;
                      return (
                        <tr key={idx} className="hover:bg-white/5">
                          <td className="px-1 py-1 text-slate-400 align-middle">{idx + 1}</td>
                          <td className="px-1 py-1 align-middle text-[12px] whitespace-nowrap">
                            <span className="group relative block max-w-full cursor-help">
                              <span className="block truncate">{String(row["EnteredAt"] || row["TradeDay"] || "")}</span>
                              <span className="pointer-events-none invisible absolute left-0 top-full z-50 mt-1 rounded border border-white/20 bg-slate-900 px-2 py-1 text-[11px] text-slate-100 shadow-lg group-hover:visible group-focus-within:visible">
                                {String(row["EnteredAt"] || row["TradeDay"] || "")}
                              </span>
                            </span>
                          </td>
                          <td className="px-1 py-1 align-middle text-[12px] whitespace-nowrap">
                            <span className="group relative block max-w-full cursor-help">
                              <span className="block truncate">{String(row["ExitedAt"] || "")}</span>
                              <span className="pointer-events-none invisible absolute left-0 top-full z-50 mt-1 rounded border border-white/20 bg-slate-900 px-2 py-1 text-[11px] text-slate-100 shadow-lg group-hover:visible group-focus-within:visible">
                                {String(row["ExitedAt"] || "")}
                              </span>
                            </span>
                          </td>
                          <td className="px-1 py-1 text-right text-emerald-300 align-middle">
                            {Number(row["PnL(Net)"] || 0).toFixed(4)}
                          </td>
                          <td className="px-1 py-1 text-right align-middle">{Number(row["Size"] || 0)}</td>
                          <td className="px-1 py-1 text-[12px] align-middle whitespace-nowrap overflow-hidden text-ellipsis">{String(row["Type"] || "")}</td>
                          <td className="px-1 py-1 text-[12px] align-middle whitespace-nowrap overflow-hidden text-ellipsis">{holdType}</td>
                          <td className="px-1 py-1 align-middle">
                            <div className="w-full rounded border border-white/10 bg-white/5 p-1">
                              <div className="grid grid-cols-2 gap-1">
                                <select
                                  value={draft.Phase}
                                  onChange={(e) => setDraftField(row as Record<string, unknown>, "Phase", e.target.value)}
                                  className="h-[30px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                                >
                                  <option value="">Phase</option>
                                  {phaseOptions.map((v) => (
                                    <option key={v} value={v}>{v}</option>
                                  ))}
                                </select>
                                <select
                                  value={draft.Context}
                                  onChange={(e) => setDraftField(row as Record<string, unknown>, "Context", e.target.value)}
                                  className="h-[30px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                                >
                                  <option value="">Context</option>
                                  {contextOptions.map((v) => (
                                    <option key={v} value={v}>{v}</option>
                                  ))}
                                </select>
                                <select
                                  value={draft.SignalBar}
                                  onChange={(e) => setDraftField(row as Record<string, unknown>, "SignalBar", e.target.value)}
                                  className="h-[30px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                                >
                                  <option value="">SignalBar</option>
                                  {signalOptions.map((v) => (
                                    <option key={v} value={v}>{v}</option>
                                  ))}
                                </select>
                                <select
                                  value={draft.TradeIntent}
                                  onChange={(e) => setDraftField(row as Record<string, unknown>, "TradeIntent", e.target.value)}
                                  className="h-[30px] rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                                >
                                  <option value="">TradeIntent</option>
                                  {tradeIntentOptions.map((v) => (
                                    <option key={v} value={v}>{v}</option>
                                  ))}
                                </select>
                                <input
                                  type="text"
                                  value={draft.Setup}
                                  list="setup-options"
                                  onChange={(e) => setDraftField(row as Record<string, unknown>, "Setup", e.target.value)}
                                  placeholder="Setup(s): Wedge | BO + Follow-through"
                                  className="h-[30px] w-full rounded border border-white/10 bg-surface px-2 text-xs text-white outline-none focus:border-accent"
                                />
                              </div>
                              <details className="mt-1 rounded border border-white/10 bg-white/5 px-2 py-1">
                                <summary className="cursor-pointer text-[11px] text-slate-300">Pick Setup Tags</summary>
                                <div className="mt-1 grid grid-cols-2 gap-1">
                                  {setupOptions.map((opt) => {
                                    const checked = splitSetupValues(draft.Setup).some((v) => v.toLowerCase() === opt.toLowerCase());
                                    return (
                                      <label key={opt} className="inline-flex items-center gap-2 text-[11px] text-slate-200">
                                        <input
                                          type="checkbox"
                                          checked={checked}
                                          onChange={() => toggleSetupChoice(row as Record<string, unknown>, opt)}
                                        />
                                        <span>{opt}</span>
                                      </label>
                                    );
                                  })}
                                </div>
                              </details>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-slate-400">Showing all trades for this range.</p>
              <datalist id="setup-options">
                {setupOptions.map((v) => (
                  <option key={v} value={v} />
                ))}
              </datalist>
            </div>
          </div>
        ) : (
          <p className="text-slate-400">No data yet.</p>
        )}
      </Card>
    </AppShell>
  );
}
