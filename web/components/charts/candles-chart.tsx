"use client";

import { Candle, TradeMarker } from "@/lib/types";
import {
  init,
  dispose,
  registerOverlay,
  CandleType,
  OverlayMode,
  LineType,
  type Chart,
  type KLineData,
  type OverlayCreate
} from "klinecharts";
import { useEffect, useRef } from "react";

// Register a lightweight text-only overlay for bar count labels
const BAR_COUNT_NAME = "barCountText";
try {
  registerOverlay({
    name: BAR_COUNT_NAME,
    totalStep: 1,
    needDefaultPointFigure: false,
    createPointFigures: ({ overlay, coordinates }) => {
      const text = String(overlay.extendData ?? "");
      const coord = coordinates[0];
      return [
        {
          type: "text",
          attrs: {
            x: coord.x,
            y: coord.y,
            text,
            align: "center",
            baseline: "top"
          },
          ignoreEvent: true
        }
      ];
    },
    styles: {
      text: {
        color: "rgba(51,65,85,0.5)",
        size: 10,
        family: "Inter, sans-serif",
        weight: 600,
        backgroundColor: "transparent",
        borderColor: "transparent"
      }
    }
  });
} catch {
  // overlay might already be registered; ignore
}

export function CandlesChart({
  data,
  trades = [],
  showTrades = true,
  heightClass = "h-[420px]",
  studyLines = []
}: {
  data: Candle[];
  trades?: TradeMarker[];
  showTrades?: boolean;
  heightClass?: string;
  studyLines?: { id: string; color: string; points: { timestamp: number; value: number }[] }[];
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<Chart | null>(null);
  const tradeOverlayIdsRef = useRef<string[]>([]);
  const studyOverlayIdsRef = useRef<string[]>([]);

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = init(containerRef.current, {
      styles: {
        candle: {
          type: CandleType.CandleSolid,
          bar: { upColor: "#5bc0be", downColor: "#ff6b6b" }
        },
        grid: { horizontal: { color: "#e5e7eb" }, vertical: { color: "#e5e7eb" } }
      }
    });
    chartRef.current = chart;
    chartRef.current?.setScrollEnabled?.(true);
    chartRef.current?.setZoomEnabled?.(true);

    const handleResize = () => chart?.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      if (containerRef.current) {
        dispose(containerRef.current);
      }
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!chartRef.current) return;
    // clear previous studies
    studyOverlayIdsRef.current.forEach((id) => {
      try {
        chartRef.current?.removeOverlay(id);
      } catch (_) {
        /* ignore */
      }
    });
    studyOverlayIdsRef.current = [];

    const barCountLines = studyLines.filter((l) => l.id === "barcount");
    const otherLines = studyLines.filter((l) => l.id !== "barcount");

    // render line-based studies (ema/vwap/etc)
    otherLines.forEach((line) => {
      for (let i = 1; i < line.points.length; i++) {
        const from = line.points[i - 1];
        const to = line.points[i];
        const id = `${line.id}-${i}`;
        studyOverlayIdsRef.current.push(id);
        const overlay: OverlayCreate = {
          id,
          name: "segment",
          lock: true,
          mode: OverlayMode.Normal,
          points: [
            { timestamp: from.timestamp, value: from.value },
            { timestamp: to.timestamp, value: to.value }
          ],
          styles: { line: { color: line.color, size: 2, style: LineType.Dashed } }
        };
        chartRef.current?.createOverlay(overlay);
      }
    });

    // render bar count as text-only overlay
    barCountLines.forEach((line) => {
      line.points.forEach((pt, idx) => {
        const id = `${line.id}-tag-${idx}`;
        studyOverlayIdsRef.current.push(id);
        const overlay: OverlayCreate = {
          id,
          name: BAR_COUNT_NAME,
          lock: true,
          mode: OverlayMode.Normal,
          extendData: String((pt as any).label ?? idx + 1),
          points: [{ timestamp: pt.timestamp, value: pt.value }]
        };
        chartRef.current?.createOverlay(overlay);
      });
    });
  }, [studyLines]);

  useEffect(() => {
    if (!chartRef.current) return;
    const kline: KLineData[] = data.map((bar) => ({
      timestamp: new Date(bar.time).getTime(),
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
      volume: bar.volume ?? 0
    }));
    chartRef.current.applyNewData(kline);

    // remove previous trade overlays
    tradeOverlayIdsRef.current.forEach((id) => {
      try {
        chartRef.current?.removeOverlay(id);
      } catch (_) {
        /* ignore */
      }
    });
    tradeOverlayIdsRef.current = [];

    if (showTrades && kline.length) {
      const orderedTrades = [...trades].sort(
        (a, b) => new Date(a.entryTime).getTime() - new Date(b.entryTime).getTime()
      );
      const snap = (tsMs: number) => {
        let nearest = Infinity;
        let price = 0;
        for (const c of kline) {
          const cTs = c.timestamp;
          if (Math.abs(cTs - tsMs) < Math.abs(nearest - tsMs)) {
            nearest = cTs;
            price = c.close;
          }
        }
        return nearest === Infinity ? undefined : { ts: nearest, price };
      };
      const points: any[] = [];
      orderedTrades.forEach((t) => {
        const entryTs = new Date(t.entryTime).getTime();
        const exitTs = new Date(t.exitTime).getTime();
        if (Number.isNaN(entryTs) || Number.isNaN(exitTs)) return;
        const entrySnap = snap(entryTs);
        const exitSnap = snap(exitTs);
        if (!entrySnap || !exitSnap) return;
        if (entrySnap.ts >= exitSnap.ts) return;
        const color = t.pnl >= 0 ? "#16a34a" : "#dc2626"; // bold green for wins, bold red for losses
        const entryVal = t.entryPrice ?? entrySnap.price;
        const exitVal = t.exitPrice ?? exitSnap.price;
        points.push(
          { timestamp: entrySnap.ts, value: entryVal, styles: { point: { shape: "triangle", color } } },
          { timestamp: exitSnap.ts, value: exitVal, styles: { point: { shape: "triangle_down", color } } }
        );
        const lineId = `trade-line-${entrySnap.ts}-${exitSnap.ts}`;
        tradeOverlayIdsRef.current.push(lineId);
        chartRef.current?.createOverlay({
          id: lineId,
          name: "segment",
          lock: true,
          mode: OverlayMode.Normal,
          points: [
            { timestamp: entrySnap.ts, value: entryVal },
            { timestamp: exitSnap.ts, value: exitVal }
          ],
          styles: { line: { color, size: 3 } }
        });
      });
      if (points.length) {
        const markerId = "trade-markers";
        tradeOverlayIdsRef.current.push(markerId);
        chartRef.current?.createOverlay({
          id: markerId,
          name: "point",
          mode: OverlayMode.Normal,
          lock: true,
          points
        });
      }
    }
  }, [data, trades, showTrades]);

  return (
    <div ref={containerRef} className={`relative ${heightClass} w-full rounded-xl border border-white/10 bg-white`} />
  );
}
