"use client";

import { AppShell } from "@/components/layout/app-shell";
import { Card } from "@/components/ui/card";
import { CandlesChart } from "@/components/charts/candles-chart";
import { SymbolSelect, symbols as SYMBOLS } from "@/components/forms/symbol-select";
import { TimeframeSelect } from "@/components/forms/timeframe-select";
import { getTradingSession } from "@/lib/api";
import { resampleCandles } from "@/lib/timeframes";
import { Candle, Timeframe, TradeMarker } from "@/lib/types";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { StatGrid } from "@/components/ui/stat-grid";

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
  const today = new Date().toISOString().slice(0, 10);
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);

  const { data, isFetching, error } = useQuery({
    queryKey: ["session", symbol, startDate, endDate],
    queryFn: () => getTradingSession({ symbol, start: startDate, end: endDate }),
    staleTime: 30_000,
    refetchOnWindowFocus: false
  });

  const viewData = useMemo(() => {
    const source = data?.future ?? [];
    return resampleCandles(source, timeframe);
  }, [data, timeframe]);

  const lastBar: Candle | undefined = viewData[viewData.length - 1];
  const tradeMarkers: TradeMarker[] =
    data?.performance?.map((p) => ({
      entryTime: String(p["EnteredAt"] || p["TradeDay"] || ""),
      exitTime: String(p["ExitedAt"] || p["TradeDay"] || ""),
      entryPrice: Number(p["EntryPrice"] || p["Entry"] || p["Open"] || 0),
      exitPrice: Number(p["ExitPrice"] || p["Exit"] || p["Close"] || 0),
      pnl: Number(p["PnL(Net)"] || 0),
      type: String(p["Type"] || ""),
      size: Number(p["Size"] || 0)
    })) || [];

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

  const ohlcRange = useMemo(() => {
    if (!viewData.length) return null;
    const open = viewData[0].open;
    const close = viewData[viewData.length - 1].close;
    const high = Math.max(...viewData.map((b) => b.high));
    const low = Math.min(...viewData.map((b) => b.low));
    return { open, high, low, close };
  }, [viewData]);


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

  const studyLines = useMemo(() => {
    const points = viewData.map((b) => ({
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
  }, [viewData, showVwap, showEma, showBarCount]);

  return (
    <AppShell active="/trading">
      <div className="grid gap-4 md:grid-cols-[1fr_280px]">
        <Card title="Controls">
          <div className="space-y-3">
            <div className="rounded-xl border border-white/10 bg-surface/80 p-3">
              <div className="flex flex-wrap items-center gap-3">
                <SymbolSelect value={symbol} onChange={setSymbol} />
                <TimeframeSelect value={timeframe} onChange={setTimeframe} />
                {[
                  { label: "Today", anchor: "today" },
                  { label: "This Week", anchor: "week" },
                  { label: "This Month", anchor: "month" }
                ].map((preset) => (
                  <button
                    key={preset.label}
                    className="h-[38px] rounded-lg border border-white/10 px-3 text-sm font-semibold text-slate-200 transition hover:border-accent/60"
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
              <div className="grid grid-cols-2 gap-2">
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
              <div className="grid grid-cols-2 gap-2">
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
            <div className="grid grid-cols-2 gap-2 text-sm text-slate-200">
              <span className="text-slate-400">Range</span>
              <span className="text-right text-white">{startDate} → {endDate}</span>
              <span className="text-slate-400">Open</span>
              <span className="text-right font-semibold text-white">{ohlcRange.open.toFixed(2)}</span>
              <span className="text-slate-400">High</span>
              <span className="text-right">{ohlcRange.high.toFixed(2)}</span>
              <span className="text-slate-400">Low</span>
              <span className="text-right">{ohlcRange.low.toFixed(2)}</span>
              <span className="text-slate-400">Close</span>
              <span className="text-right font-semibold text-white">{ohlcRange.close.toFixed(2)}</span>
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
        <div className="fixed inset-0 z-50 bg-black/80 p-4">
          <div className="mx-auto flex max-w-6xl flex-col gap-3 rounded-2xl border border-white/10 bg-surface/90 p-4 shadow-2xl">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.2em] text-accent">Price Action</p>
                <p className="text-lg font-semibold text-white">
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
            <CandlesChart
              data={viewData}
              trades={tradeMarkers}
              showTrades={showTrades}
              heightClass="h-[80vh]"
              studyLines={studyLines}
            />
          </div>
        </div>
      )}

      <Card title="Trades Stats" className="mt-2">
        {data ? (
          <div className="space-y-4">
            <StatGrid stats={{ ...(data.stats || {}), duration_bins: durationBins }} />
              <div className="space-y-2 rounded-lg border border-white/5 p-3">
              <div className="flex flex-wrap gap-3 text-sm text-slate-200">
                <label className="flex items-center gap-2">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Direction</span>
                  <select
                    className="h-[38px] rounded-lg border border-white/10 bg-surface px-3 text-sm text-white outline-none focus:border-accent"
                    value={directionFilter}
                    onChange={(e) => setDirectionFilter(e.target.value)}
                  >
                    <option value="">All</option>
                    <option value="Long">Long</option>
                    <option value="Short">Short</option>
                  </select>
                </label>
                <label className="flex items-center gap-2">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Type</span>
                  <select
                    className="h-[38px] rounded-lg border border-white/10 bg-surface px-3 text-sm text-white outline-none focus:border-accent"
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                  >
                    <option value="">All</option>
                    <option value="Sc">Sc</option>
                    <option value="Sc/w">Sc/w</option>
                    <option value="Sw">Sw</option>
                  </select>
                </label>
                <label className="flex items-center gap-2">
                  <span className="text-xs uppercase tracking-[0.2em] text-slate-400">Size</span>
                  <select
                    className="h-[38px] rounded-lg border border-white/10 bg-surface px-3 text-sm text-white outline-none focus:border-accent"
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
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-white/5 text-sm text-slate-200">
                  <thead className="bg-white/5 text-xs uppercase tracking-wide text-slate-400">
                    <tr>
                      <th className="px-3 py-2 text-left">#</th>
                      <th className="px-3 py-2 text-left">Entry</th>
                      <th className="px-3 py-2 text-left">Exit</th>
                      <th className="px-3 py-2 text-right">PnL(Net)</th>
                      <th className="px-3 py-2 text-right">Size</th>
                      <th className="px-3 py-2 text-left">Direction</th>
                      <th className="px-3 py-2 text-left">Type</th>
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
                            ? "Sc"
                            : mins < 30
                              ? "Sc/w"
                              : "Sw";
                      const direction = String(row["Type"] || "");
                      const sizeVal = Number(row["Size"] || 0);

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
                          <td className="px-3 py-2 text-slate-400">{idx + 1}</td>
                          <td className="px-3 py-2">{String(row["EnteredAt"] || row["TradeDay"] || "")}</td>
                          <td className="px-3 py-2">{String(row["ExitedAt"] || "")}</td>
                          <td className="px-3 py-2 text-right text-emerald-300">
                            {Number(row["PnL(Net)"] || 0).toFixed(2)}
                          </td>
                          <td className="px-3 py-2 text-right">{Number(row["Size"] || 0)}</td>
                          <td className="px-3 py-2">{String(row["Type"] || "")}</td>
                          <td className="px-3 py-2">{holdType}</td>
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
    </AppShell>
  );
}
