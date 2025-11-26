import { Candle, Timeframe } from "./types";

const timeframeToMs: Record<Timeframe, number> = {
  "5m": 5 * 60 * 1000,
  "15m": 15 * 60 * 1000,
  "30m": 30 * 60 * 1000,
  "1h": 60 * 60 * 1000,
  "4h": 4 * 60 * 60 * 1000,
  "1d": 24 * 60 * 60 * 1000,
  "1w": 7 * 24 * 60 * 60 * 1000
};

function startOfWeek(ts: number) {
  const d = new Date(ts);
  const day = d.getUTCDay();
  const diff = (day + 6) % 7; // monday=0
  d.setUTCHours(0, 0, 0, 0);
  return d.getTime() - diff * 24 * 60 * 60 * 1000;
}

function inferBaseIntervalMs(candles: Candle[]): number {
  const times = candles
    .map((c) => new Date(c.time).getTime())
    .filter((t) => !Number.isNaN(t))
    .sort((a, b) => a - b);
  const diffs: number[] = [];
  for (let i = 1; i < times.length; i++) {
    const d = times[i] - times[i - 1];
    if (d > 0) diffs.push(d);
  }
  if (!diffs.length) return 5 * 60 * 1000;
  diffs.sort((a, b) => a - b);
  return diffs[Math.floor(diffs.length / 2)] || 5 * 60 * 1000;
}

function resampleSequential(candles: Candle[], targetMs: number): Candle[] {
  if (!candles.length) return [];
  const baseMs = inferBaseIntervalMs(candles);
  const barsPerBucket = Math.max(1, Math.round(targetMs / baseMs));
  const sorted = [...candles].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());

  const buckets: Candle[] = [];
  let current: Candle | null = null;
  let count = 0;
  let lastTs = 0;

  for (const bar of sorted) {
    const ts = new Date(bar.time).getTime();
    const gap = ts - lastTs;
    const newBucket = !current || gap > baseMs * 1.5 || count >= barsPerBucket;
    if (newBucket) {
      if (current) buckets.push(current);
      current = {
        time: bar.time,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume ?? 0
      };
      count = 1;
    } else if (current) {
      current.high = Math.max(current.high, bar.high);
      current.low = Math.min(current.low, bar.low);
      current.close = bar.close;
      current.volume = (current.volume ?? 0) + (bar.volume ?? 0);
      count += 1;
    }
    lastTs = ts;
  }
  if (current) buckets.push(current);
  return buckets;
}

export function resampleCandles(candles: Candle[], target: Timeframe): Candle[] {
  if (target === "5m") return candles;
  const bucketMs = timeframeToMs[target];
  // For intraday multi-hour buckets, resample sequentially to avoid clock anchoring
  if (["15m", "30m", "1h", "4h"].includes(target)) {
    return resampleSequential(candles, bucketMs);
  }
  const buckets = new Map<number, Candle>();

  for (const bar of candles) {
    const ts = new Date(bar.time).getTime();
    const bucketStart =
      target === "1w"
        ? startOfWeek(ts)
        : target === "1d"
          ? (() => {
              const d = new Date(ts);
              d.setUTCHours(0, 0, 0, 0);
              return d.getTime();
            })()
          : Math.floor(ts / bucketMs) * bucketMs;

    const existing = buckets.get(bucketStart);
    if (!existing) {
      buckets.set(bucketStart, {
        time: new Date(bucketStart).toISOString(),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume ?? 0
      });
    } else {
      existing.high = Math.max(existing.high, bar.high);
      existing.low = Math.min(existing.low, bar.low);
      existing.close = bar.close;
      existing.volume = (existing.volume ?? 0) + (bar.volume ?? 0);
    }
  }

  return Array.from(buckets.entries())
    .sort((a, b) => a[0] - b[0])
    .map(([, bar]) => bar);
}

export const TIMEFRAME_OPTIONS: { label: string; value: Timeframe }[] = [
  { label: "5m", value: "5m" },
  { label: "15m", value: "15m" },
  { label: "30m", value: "30m" },
  { label: "1H", value: "1h" },
  { label: "4H", value: "4h" },
  { label: "1D", value: "1d" },
  { label: "1W", value: "1w" }
];
