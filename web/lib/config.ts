import type { Timeframe } from "./types";

export type SymbolConfig = {
  symbol: string;
  data_path: string;
  performance_path: string;
  asset_class: string;
  source?: Record<string, unknown>;
  exchange?: string;
  timezone?: string;
};

export type ConfigResponse = {
  symbols: SymbolConfig[];
  timeframes?: Timeframe[];
  playback_speeds?: number[];
};

export async function fetchConfig(): Promise<ConfigResponse> {
  const res = await fetch("/api/config", { cache: "no-store" });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg || "Failed to load config");
  }
  return res.json();
}
