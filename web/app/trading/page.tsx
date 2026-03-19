"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { CandlesChart } from "@/components/charts/candles-chart";
import { SymbolSelect } from "@/components/forms/symbol-select";
import { TimeframeSelect } from "@/components/forms/timeframe-select";
import { getDayPlan, getJournalLive, getMatchingLinks, getTradingSession } from "@/lib/api";
import { resampleCandles } from "@/lib/timeframes";
import { Candle, LiveJournalRow, Timeframe, TradeMarker } from "@/lib/types";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { StatGrid } from "@/components/ui/stat-grid";
import dynamic from "next/dynamic";
const PlaybackControls = dynamic(() => import("@/components/ui/playback-controls").then((m) => m.PlaybackControls), { ssr: false });
type PlaybackState = import("@/components/ui/playback-controls").PlaybackState;

function localDateYmd(d: Date): string {
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

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
  const [activeJournalTradeId, setActiveJournalTradeId] = useState("");
  const today = localDateYmd(new Date());
  const [planDate, setPlanDate] = useState(today);
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);

  const { data, isFetching, error } = useQuery({
    queryKey: ["session", symbol, startDate, endDate],
    queryFn: () => getTradingSession({ symbol, start: startDate, end: endDate }),
    staleTime: 30_000,
    refetchOnWindowFocus: false
  });
  const { data: dayPlanRange } = useQuery({
    queryKey: ["day-plan-range", startDate, endDate],
    queryFn: () => getDayPlan({ start: startDate, end: endDate }),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  const { data: liveJournalRange } = useQuery({
    queryKey: ["live-journal-range", startDate, endDate],
    queryFn: () => getJournalLive({ start: startDate, end: endDate }),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  const { data: linkRange } = useQuery({
    queryKey: ["matching-links-range", startDate, endDate],
    queryFn: () => getMatchingLinks({ start: startDate, end: endDate }),
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
  });
  const dayPlanByDate = useMemo(() => {
    const out = new Map<string, Record<string, unknown>>();
    (dayPlanRange?.rows ?? []).forEach((r) => {
      const day = String(r["Date"] || "").trim();
      if (day) out.set(day, r);
    });
    return out;
  }, [dayPlanRange?.rows]);
  const selectedDayPlan = useMemo(() => dayPlanByDate.get(planDate), [dayPlanByDate, planDate]);
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
        out.push(localDateYmd(cur));
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

  const tradeIdOf = (row: Record<string, unknown>): string =>
    String(row["trade_id"] || row["tradeId"] || "").trim();

  const holdTypeOf = (row: Record<string, unknown>): string => {
    const enter = new Date(String(row["EnteredAt"] || "")).getTime();
    const exit = new Date(String(row["ExitedAt"] || "")).getTime();
    const mins = !Number.isNaN(enter) && !Number.isNaN(exit) ? (exit - enter) / 60000 : null;
    if (mins == null) return "N/A";
    if (mins <= 5) return "Scalp";
    if (mins < 30) return "Scalp/Swing";
    return "Swing";
  };

  const filteredPerformance = useMemo(
    () =>
      (data?.performance || []).filter((r) => {
        const row = r as Record<string, unknown>;
        const direction = String(row["Type"] || "");
        const holdType = holdTypeOf(row);
        const sizeVal = Number(row["Size"] || 0);
        const dirOk = !directionFilter || direction === directionFilter;
        const typeOk = !typeFilter || holdType === typeFilter;
        const sizeOk =
          !sizeFilter ||
          (sizeFilter === "S" && sizeVal <= 2) ||
          (sizeFilter === "M" && sizeVal > 2 && sizeVal <= 5) ||
          (sizeFilter === "L" && sizeVal > 5);
        return dirOk && typeOk && sizeOk;
      }),
    [data?.performance, directionFilter, typeFilter, sizeFilter]
  );

  const liveJournalById = useMemo(() => {
    const out = new Map<string, LiveJournalRow>();
    (liveJournalRange?.rows || []).forEach((r) => {
      const id = String(r.journal_id || "").trim();
      if (id) out.set(id, r);
    });
    return out;
  }, [liveJournalRange?.rows]);

  const journalIdsByTradeId = useMemo(() => {
    const out = new Map<string, string[]>();
    (linkRange?.rows || []).forEach((row) => {
      const tradeId = String((row as Record<string, unknown>)["trade_id"] || "").trim();
      const journalId = String((row as Record<string, unknown>)["journal_id"] || "").trim();
      if (!tradeId || !journalId) return;
      const list = out.get(tradeId) || [];
      if (!list.includes(journalId)) list.push(journalId);
      out.set(tradeId, list);
    });
    return out;
  }, [linkRange?.rows]);

  const activeJournalRows = useMemo(
    () => (journalIdsByTradeId.get(activeJournalTradeId) || []).map((id) => liveJournalById.get(id)).filter(Boolean) as LiveJournalRow[],
    [activeJournalTradeId, journalIdsByTradeId, liveJournalById]
  );
  const activeNeedsReconfirmCount = useMemo(
    () =>
      activeJournalRows.filter((j) => String(j.MatchStatus || "").trim().toLowerCase() === "needs_reconfirm").length,
    [activeJournalRows]
  );


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
                      const startIso = localDateYmd(start);
                      const endIso = localDateYmd(now);
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
                <div className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs">
                  <p className="text-slate-400">Date</p>
                  <p className="text-white">{planDate || "-"}</p>
                </div>
                <div className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs">
                  <p className="text-slate-400">Bias</p>
                  <p className="text-white">{String(selectedDayPlan?.["Bias"] || "-")}</p>
                </div>
                <div className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs">
                  <p className="text-slate-400">Expected Day Type</p>
                  <p className="text-white">{String(selectedDayPlan?.["ExpectedDayType"] || "-")}</p>
                </div>
                <div className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs">
                  <p className="text-slate-400">Actual Day Type</p>
                  <p className="text-white">{String(selectedDayPlan?.["ActualDayType"] || "-")}</p>
                </div>
                <div className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs sm:col-span-2">
                  <p className="text-slate-400">Key Levels / HTF Context</p>
                  <p className="whitespace-pre-wrap text-white">{String(selectedDayPlan?.["KeyLevelsHTFContext"] || "-")}</p>
                </div>
                <div className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs sm:col-span-2">
                  <p className="text-slate-400">Primary Plan</p>
                  <p className="whitespace-pre-wrap text-white">{String(selectedDayPlan?.["PrimaryPlan"] || "-")}</p>
                </div>
                <div className="rounded border border-white/10 bg-surface px-2 py-1.5 text-xs sm:col-span-2">
                  <p className="text-slate-400">Avoidance Plan</p>
                  <p className="whitespace-pre-wrap text-white">{String(selectedDayPlan?.["AvoidancePlan"] || "-")}</p>
                </div>
              </div>
            </div>
              <div className="space-y-2 rounded-lg border border-white/5 p-3">
              <div className="rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-xs text-slate-300">
                Trades are linked to journal record(s). Use View to inspect attached journal details.
              </div>
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
                {filteredPerformance.map((row, idx) => {
                  const holdType = holdTypeOf(row as Record<string, unknown>);
                  const direction = String(row["Type"] || "");
                  const sizeVal = Number(row["Size"] || 0);
                  const tradeId = tradeIdOf(row as Record<string, unknown>);
                  const linkedCount = tradeId ? (journalIdsByTradeId.get(tradeId) || []).length : 0;
                  return (
                    <div key={idx} className="rounded-lg border border-white/10 bg-white/5 p-2 text-xs text-slate-200">
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">#</span><span>{idx + 1}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Entry</span><span className="break-words">{String(row["EnteredAt"] || row["TradeDay"] || "")}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Exit</span><span className="break-words">{String(row["ExitedAt"] || "")}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">PnL(Net)</span><span className="text-emerald-300">{Number(row["PnL(Net)"] || 0).toFixed(4)}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Size</span><span>{sizeVal}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Direction</span><span>{direction}</span></div>
                      <div className="grid grid-cols-[96px_1fr] gap-2 py-0.5"><span className="text-slate-400">Type</span><span>{holdType}</span></div>
                      <div className="grid grid-cols-[96px_1fr] items-center gap-2 py-0.5">
                        <span className="text-slate-400">Journals</span>
                        <div className="flex items-center gap-2">
                          <span>{linkedCount}</span>
                          <button
                            type="button"
                            disabled={!tradeId || linkedCount === 0}
                            onClick={() => setActiveJournalTradeId(tradeId)}
                            className="rounded border border-accent/40 px-2 py-0.5 text-[11px] text-accent disabled:border-white/15 disabled:text-slate-500"
                          >
                            View
                          </button>
                        </div>
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
                      <th className="px-1 py-1 text-left">Journals</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {filteredPerformance.map((row, idx) => {
                      const holdType = holdTypeOf(row as Record<string, unknown>);
                      const direction = String(row["Type"] || "");
                      const sizeVal = Number(row["Size"] || 0);
                      const tradeId = tradeIdOf(row as Record<string, unknown>);
                      const linkedCount = tradeId ? (journalIdsByTradeId.get(tradeId) || []).length : 0;
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
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-slate-300">{linkedCount}</span>
                              <button
                                type="button"
                                disabled={!tradeId || linkedCount === 0}
                                onClick={() => setActiveJournalTradeId(tradeId)}
                                className="rounded border border-accent/40 px-2 py-0.5 text-[11px] text-accent disabled:border-white/15 disabled:text-slate-500"
                              >
                                View
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-slate-400">Showing all trades for this range.</p>
            </div>
          </div>
        ) : (
          <p className="text-slate-400">No data yet.</p>
        )}
      </Card>
      {activeJournalTradeId ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-3">
          <div className="w-full max-w-4xl rounded-xl border border-white/15 bg-surface p-4 shadow-2xl">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.14em] text-slate-400">Attached Journals</p>
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm text-white">Trade ID: {activeJournalTradeId}</p>
                  {activeNeedsReconfirmCount > 0 ? (
                    <span className="rounded-full border border-amber-300/50 bg-amber-500/15 px-2 py-0.5 text-[11px] text-amber-200">
                      needs reconfirm: {activeNeedsReconfirmCount}
                    </span>
                  ) : null}
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActiveJournalTradeId("")}
                className="rounded border border-white/20 px-2 py-1 text-xs text-slate-200"
              >
                Close
              </button>
            </div>
            <div className="max-h-[70vh] space-y-3 overflow-auto pr-1">
              {activeJournalRows.length ? (
                activeJournalRows.map((j) => (
                  <div key={String(j.journal_id || "")} className="rounded border border-white/10 bg-white/5 p-3 text-xs text-slate-200">
                    <div className="grid gap-2 md:grid-cols-4">
                      <p><span className="text-slate-400">Journal ID:</span> {String(j.journal_id || "")}</p>
                      <p><span className="text-slate-400">TradeDay:</span> {String(j.TradeDay || "")}</p>
                      <p><span className="text-slate-400">Seq:</span> {String(j.SeqInDay || "")}</p>
                      <p><span className="text-slate-400">Contract:</span> {String(j.ContractName || "")}</p>
                      <p><span className="text-slate-400">Direction:</span> {String(j.Direction || "")}</p>
                      <p><span className="text-slate-400">Size:</span> {String(j.Size || "")}</p>
                      <p><span className="text-slate-400">Intent:</span> {String(j.TradeIntent || "")}</p>
                      <p className="flex items-center gap-2">
                        <span className="text-slate-400">Match:</span>
                        {String(j.MatchStatus || "").trim().toLowerCase() === "needs_reconfirm" ? (
                          <span className="rounded-full border border-amber-300/50 bg-amber-500/15 px-2 py-0.5 text-[11px] text-amber-200">
                            needs_reconfirm
                          </span>
                        ) : String(j.MatchStatus || "").trim() ? (
                          <span className="rounded-full border border-emerald-300/40 bg-emerald-500/15 px-2 py-0.5 text-[11px] text-emerald-200">
                            {String(j.MatchStatus || "")}
                          </span>
                        ) : (
                          <span>-</span>
                        )}
                      </p>
                    </div>
                    <div className="mt-2 grid gap-2 md:grid-cols-3">
                      <p><span className="text-slate-400">Entry:</span> {String(j.EntryPrice || "-")}</p>
                      <p><span className="text-slate-400">TP:</span> {String(j.TakeProfitPrice || "-")}</p>
                      <p><span className="text-slate-400">SL:</span> {String(j.StopLossPrice || "-")}</p>
                      <p><span className="text-slate-400">Exit:</span> {String(j.ExitPrice || "-")}</p>
                      <p><span className="text-slate-400">Expected Risk:</span> {String(j.PotentialRiskUSD || "-")}</p>
                      <p><span className="text-slate-400">Expected Reward:</span> {String(j.PotentialRewardUSD || "-")}</p>
                    </div>
                    <div className="mt-2 rounded border border-white/10 bg-surface p-2">
                      <p className="mb-1 text-[10px] uppercase tracking-[0.12em] text-slate-400">Detail Rows</p>
                      {Array.isArray(j.adjustments) && j.adjustments.length ? (
                        <div className="space-y-1 text-[11px]">
                          {j.adjustments.map((a, i) => (
                            <p key={String(a.adjustment_id || `${j.journal_id}-adj-${i}`)}>
                              L{String(a.LegIndex || i + 1)} qty {String(a.Qty || "")} @ {String(a.EntryPrice || "")} tp {String(a.TakeProfitPrice || "")} sl {String(a.StopLossPrice || "")}{String(a.ExitPrice || "").trim() ? ` exit ${String(a.ExitPrice || "")}` : ""}
                            </p>
                          ))}
                        </div>
                      ) : (
                        <p className="text-[11px] text-slate-400">No detail rows.</p>
                      )}
                    </div>
                    {String(j.Notes || "").trim() ? (
                      <p className="mt-2 text-[11px]"><span className="text-slate-400">Notes:</span> {String(j.Notes || "")}</p>
                    ) : null}
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-400">No journal rows loaded for this trade link in selected date range.</p>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </AppShell>
  );
}
