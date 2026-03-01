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
  insights_defaults?: {
    rule_compliance?: {
      max_trades_per_day?: number;
      max_consecutive_losses?: number;
      max_daily_loss?: number;
      big_loss_threshold?: number;
      max_trades_after_big_loss?: number;
    };
  };
  portfolio?: {
    initial_net_liq: number;
    start_date: string;
    risk_free_rate: number;
  };
};

export async function fetchConfig(): Promise<ConfigResponse> {
  const res = await fetch("/api/config", { cache: "no-store" });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg || "Failed to load config");
  }
  return res.json();
}
