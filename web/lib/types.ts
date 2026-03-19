export type Timeframe = "5m" | "15m" | "30m" | "1h" | "4h" | "1d" | "1w";

export interface Candle {
  time: string; // ISO string
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

export interface PerformanceRecord {
  [key: string]: string | number | null;
}

export interface AnalysisPayload {
  granularity?: string;
  window?: number;
  params?: Record<string, unknown>;
  symbol?: string;
  start_date?: string;
  end_date?: string;
  include_unmatched?: boolean;
}

export interface AnalysisSeriesPoint {
  [key: string]: string | number | null;
}

export type AnalysisResponse =
  | AnalysisSeriesPoint[]
  | {
      theoretical: AnalysisSeriesPoint[];
      actual: AnalysisSeriesPoint[];
    };

export interface InsightsPayload {
  symbol?: string;
  start_date?: string;
  end_date?: string;
  params?: Record<string, unknown>;
  include_unmatched?: boolean;
}

export interface InsightsResponse {
  applied_config?: Record<string, unknown>;
  analysis_scope?: Record<string, string | number>;
  setup_journal: AnalysisSeriesPoint[];
  setup_quality?: Record<string, string | number | Record<string, number>>;
  rule_compliance: {
    summary: Record<string, string | number>;
    daily: AnalysisSeriesPoint[];
  };
  execution_quality?: {
    by_entry_hour: AnalysisSeriesPoint[];
    by_hold_bucket: AnalysisSeriesPoint[];
  };
  playbook: {
    highlights: AnalysisSeriesPoint[];
    stop_doing: AnalysisSeriesPoint[];
    action_items: AnalysisSeriesPoint[];
    rationale?: {
      breach_counts: Record<string, number>;
      worst_entry_hour: AnalysisSeriesPoint | null;
      worst_hold_bucket: AnalysisSeriesPoint | null;
      best_setup: AnalysisSeriesPoint | null;
      weak_setup: AnalysisSeriesPoint | null;
    };
  };
  day_plan_review?: {
    summary: Record<string, string | number>;
    daily: AnalysisSeriesPoint[];
  };
  monthly_report: {
    summary: Record<string, string | number>;
    focus_points: string[];
    markdown?: string;
    applied_config?: Record<string, unknown>;
    analysis_scope?: Record<string, string | number>;
  };
  llm_prompt_markdown?: string;
}

export interface TradingSession {
  future: Candle[];
  performance: PerformanceRecord[];
  stats: {
    win_loss: { label: string; value: number }[];
    financial_metrics: Record<string, number | string>;
    win_loss_by_type: { Type: string; Wins: number; Losses: number }[];
    streak_data: PerformanceRecord[];
    duration_data: number[];
    size_counts: { Size: number; Count: number }[];
  };
}

export interface TradeMarker {
  entryTime: string;
  exitTime: string;
  entryPrice: number;
  exitPrice: number;
  pnl: number;
  type?: string;
  size?: number;
}

export interface JournalAdjustment {
  adjustment_id?: string;
  LegIndex?: number | string;
  Qty: string;
  EntryPrice: string;
  TakeProfitPrice: string;
  StopLossPrice: string;
  ExitPrice?: string;
  EnteredAt?: string;
  ExitedAt?: string;
  RiskUSD?: string;
  RewardUSD?: string;
  WinLossRatio?: string;
  Note?: string;
}

export interface LiveJournalRow {
  journal_id?: string;
  TradeDay: string;
  SeqInDay?: number | string;
  ContractName?: string;
  Phase: string;
  Context: string;
  Setup: string;
  SignalBar: string;
  TradeIntent: string;
  Direction: "Long" | "Short";
  Size: number | string;
  MaxLossUSD?: number | string;
  EnteredAt?: string;
  ExitedAt?: string;
  EntryPrice?: number | string;
  TakeProfitPrice?: number | string;
  StopLossPrice?: number | string;
  ExitPrice?: number | string;
  PotentialRiskUSD?: number | string;
  PotentialRewardUSD?: number | string;
  WinLossRatio?: number | string;
  RuleStatus?: string;
  Notes?: string;
  MatchStatus?: string;
  adjustments_mode?: "append" | "replace";
  adjustments?: JournalAdjustment[];
}
