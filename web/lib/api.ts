import {
  AnalysisPayload,
  AnalysisResponse,
  Candle,
  InsightsPayload,
  InsightsResponse,
  LiveJournalRow,
  PerformanceRecord,
} from "./types";
import type { TradingSession } from "./types";

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function getApiBase(): string {
  const envBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  // Prefer explicit env (absolute URL). If it's a relative path, anchor it to the current origin in the browser.
  if (envBase) {
    if (envBase.startsWith("http://") || envBase.startsWith("https://")) {
      return envBase.replace(/\/+$/, "");
    }
    if (typeof window !== "undefined") {
      return new URL(envBase, window.location.origin).toString().replace(/\/+$/, "");
    }
  }
  // Browser fallback: same-origin
  if (typeof window !== "undefined") {
    // Common local setup: Next on :3000 and Flask API on :8050.
    if (window.location.port === "3000") {
      return "http://localhost:8050";
    }
    return window.location.origin;
  }
  // SSR/dev fallback
  return "http://127.0.0.1:5000";
}

const API_BASE = getApiBase();

const basicUser = process.env.NEXT_PUBLIC_BASIC_AUTH_USER;
const basicPass = process.env.NEXT_PUBLIC_BASIC_AUTH_PASS;
const basicAuthHeader =
  basicUser && basicPass
    ? "Basic " +
      (typeof window === "undefined"
        ? Buffer.from(`${basicUser}:${basicPass}`).toString("base64")
        : btoa(`${basicUser}:${basicPass}`))
    : null;

async function handleResponse<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!res.ok) {
    let payload: { error?: string; code?: string; message?: string } | null = null;
    try {
      payload = JSON.parse(text) as { error?: string; code?: string; message?: string };
    } catch {
      payload = null;
    }
    const isHtmlError = /^\s*<!doctype html/i.test(text) || /^\s*<html/i.test(text);
    const msg = payload?.error || payload?.message || (isHtmlError ? `Server error (${res.status}) from ${res.url}` : text || res.statusText);
    throw new ApiError(msg, res.status, payload?.code);
  }
  try {
    return JSON.parse(text) as T;
  } catch {
    const snippet = text.slice(0, 140).replace(/\s+/g, " ").trim();
    throw new ApiError(
      `Expected JSON but got non-JSON (status ${res.status}) from ${res.url}. Payload starts with: ${snippet}`,
      res.status
    );
  }
}

function withAuth(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers || {});
  if (basicAuthHeader) {
    headers.set("Authorization", basicAuthHeader);
  }
  return { ...init, headers };
}

export async function getCandles(params: { symbol: string; start?: string; end?: string }): Promise<Candle[]> {
  const url = new URL("/api/candles", API_BASE);
  url.searchParams.set("symbol", params.symbol);
  if (params.start) url.searchParams.set("start", params.start);
  if (params.end) url.searchParams.set("end", params.end);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse<Candle[]>(res);
}

export async function getCombinedPerformance(): Promise<PerformanceRecord[]> {
  const url = new URL("/api/performance/combined", API_BASE);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse<PerformanceRecord[]>(res);
}

export async function postAnalysis(metric: string, payload: AnalysisPayload): Promise<AnalysisResponse> {
  const url = new URL(`/api/analysis/${metric}`, API_BASE);
  const res = await fetch(url.toString(), withAuth({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {})
  }));
  return handleResponse<AnalysisResponse>(res);
}

export async function postInsights(payload: InsightsPayload): Promise<InsightsResponse> {
  const url = new URL("/api/insights", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    })
  );
  return handleResponse<InsightsResponse>(res);
}

export async function getTradingSession(params: { symbol: string; start?: string; end?: string }): Promise<TradingSession> {
  const url = new URL("/api/trading/session", API_BASE);
  url.searchParams.set("symbol", params.symbol);
  if (params.start) url.searchParams.set("start", params.start);
  if (params.end) url.searchParams.set("end", params.end);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse<TradingSession>(res);
}

export async function getTradingDefaultDay(params: { symbol: string }): Promise<{ ok: boolean; day: string; source?: string }> {
  const url = new URL("/api/trading/default-day", API_BASE);
  url.searchParams.set("symbol", params.symbol);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse(res);
}

export async function postTradingLlmPrompt(payload: {
  symbol: string;
  start?: string;
  end?: string;
  timeframe?: string;
  show_trades?: boolean;
  show_vwap?: boolean;
  show_ema?: boolean;
  show_bar_count?: boolean;
  direction_filter?: string;
  type_filter?: string;
  size_filter?: string;
  plan_date?: string;
}): Promise<{ ok: boolean; markdown: string; context: Record<string, unknown> }> {
  const url = new URL("/api/trading/llm-prompt", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    })
  );
  return handleResponse(res);
}

export async function getPortfolio(): Promise<any> {
  const url = new URL("/api/portfolio", API_BASE);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse<any>(res);
}

export async function postPortfolioAdjust(payload: { reason: "deposit" | "withdraw"; amount: number; date: string }): Promise<any> {
  const url = new URL("/api/portfolio/adjust", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
  );
  return handleResponse<any>(res);
}

export async function postJournalSetupTags(payload: {
  rows: Array<{
    trade_id?: string;
    TradeDay?: string;
    ContractName?: string;
    IntradayIndex?: string | number;
    Phase?: string;
    Context?: string;
    SignalBar?: string;
    TradeIntent?: string;
    setups: string[] | string;
  }>;
}): Promise<{ ok: boolean; updated: number; inserted: number }> {
  const url = new URL("/api/journal/tags", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? { rows: [] }),
    })
  );
  return handleResponse<{ ok: boolean; updated: number; inserted: number }>(res);
}

export async function getTagTaxonomy(): Promise<{
  phase: Array<{ value: string; hint?: string; order?: number }>;
  context: Array<{ value: string; hint?: string; order?: number }>;
  setup: Array<{ value: string; hint?: string; order?: number }>;
  signal_bar: Array<{ value: string; hint?: string; order?: number }>;
  trade_intent: Array<{ value: string; hint?: string; order?: number }>;
}> {
  const url = new URL("/api/tags/taxonomy", API_BASE);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse(res);
}

export async function getDayPlan(params?: { start?: string; end?: string }): Promise<{ rows: Array<Record<string, unknown>> }> {
  const url = new URL("/api/day-plan", API_BASE);
  if (params?.start) url.searchParams.set("start", params.start);
  if (params?.end) url.searchParams.set("end", params.end);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse(res);
}

export async function postDayPlan(payload: {
  rows: Array<{
    Date: string;
    Bias?: string;
    ExpectedDayType?: string;
    ActualDayType?: string;
    KeyLevelsHTFContext?: string;
    PrimaryPlan?: string;
    AvoidancePlan?: string;
  }>;
}): Promise<{ ok: boolean; updated: number; inserted: number }> {
  const url = new URL("/api/day-plan", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? { rows: [] }),
    })
  );
  return handleResponse(res);
}

export async function getDayPlanTaxonomy(): Promise<{
  bias: Array<{ value: string; hint?: string; order?: number }>;
  expected_day_type: Array<{ value: string; hint?: string; order?: number }>;
  actual_day_type: Array<{ value: string; hint?: string; order?: number }>;
}> {
  const url = new URL("/api/day-plan/taxonomy", API_BASE);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse(res);
}

export async function getJournalLiveMeta(): Promise<{
  phase: Array<{ value: string; hint?: string; order?: number }>;
  context: Array<{ value: string; hint?: string; order?: number }>;
  setup: Array<{ value: string; hint?: string; order?: number }>;
  signal_bar: Array<{ value: string; hint?: string; order?: number }>;
  trade_intent: Array<{ value: string; hint?: string; order?: number }>;
  direction: Array<{ value: string }>;
  contracts: Array<{ symbol: string; point_value: number }>;
}> {
  const url = new URL("/api/journal/live/meta", API_BASE);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse(res);
}

export async function getJournalLive(params?: { start?: string; end?: string }): Promise<{ rows: LiveJournalRow[] }> {
  const url = new URL("/api/journal/live", API_BASE);
  if (params?.start) url.searchParams.set("start", params.start);
  if (params?.end) url.searchParams.set("end", params.end);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse(res);
}

export async function postJournalLive(payload: { rows: LiveJournalRow[] }): Promise<{ ok: boolean; inserted: number; updated: number }> {
  const url = new URL("/api/journal/live", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? { rows: [] }),
    })
  );
  return handleResponse(res);
}

export async function deleteJournalLive(payload: { journal_id: string }): Promise<{ ok: boolean; deleted: number; deleted_adjustments: number }> {
  const url = new URL("/api/journal/live", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    })
  );
  return handleResponse(res);
}

export async function postTradeUploadParsePreview(
  files: File[],
  options?: { archiveRaw?: boolean }
): Promise<{
  ok: boolean;
  can_continue: boolean;
  hard_blocked: boolean;
  parse_logs: Array<Record<string, unknown>>;
  unparseable_rows: Array<Record<string, unknown>>;
  parsed_trades: Array<Record<string, unknown>>;
  execution_pool: Array<Record<string, unknown>>;
  parsed_range: { start: string; end: string; days: string[] };
  archived_files?: string[];
  removed_files?: string[];
}> {
  const url = new URL("/api/trade-upload/parse-preview", API_BASE);
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  form.append("archive_raw", options?.archiveRaw ? "true" : "false");
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      body: form,
    })
  );
  return handleResponse(res);
}

export async function postTradeUploadCommit(payload: {
  parsed_trades: Array<Record<string, unknown>>;
}): Promise<{
  ok: boolean;
  merged: boolean;
  rows_before: number;
  rows_after: number;
  rows_delta: number;
}> {
  const url = new URL("/api/trade-upload/commit", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? { parsed_trades: [] }),
    })
  );
  return handleResponse(res);
}

export async function postTradeUploadReconcilePreview(payload: {
  parsed_trades: Array<Record<string, unknown>>;
}): Promise<{
  ok: boolean;
  parsed_range: { start: string; end: string; days: string[] };
  parsed_trades: Array<Record<string, unknown>>;
  journal_rows: LiveJournalRow[];
  suggestions: Array<Record<string, unknown>>;
  summary: {
    trade_count: number;
    journal_count: number;
    suggestion_count: number;
    recommended_count: number;
    hard_conflict_count: number;
  };
}> {
  const url = new URL("/api/trade-upload/reconcile-preview", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? { parsed_trades: [] }),
    })
  );
  return handleResponse(res);
}

export async function postMatchingCommit(payload: {
  parsed_trades: Array<Record<string, unknown>>;
  links: Array<Record<string, unknown>>;
  replace_for_journal?: boolean;
}): Promise<{
  ok: boolean;
  merged: boolean;
  rows_before: number;
  rows_after: number;
  rows_delta: number;
  matches_inserted: number;
  matches_inactivated: number;
}> {
  const url = new URL("/api/journal/matching/commit", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? { parsed_trades: [], links: [] }),
    })
  );
  return handleResponse(res);
}

export async function getMatchingRelinkPreview(params: { start: string; end: string }): Promise<{
  ok: boolean;
  can_continue: boolean;
  hard_blocked: boolean;
  parse_logs: Array<Record<string, unknown>>;
  unparseable_rows: Array<Record<string, unknown>>;
  parsed_trades: Array<Record<string, unknown>>;
  parsed_range: { start: string; end: string; days: string[] };
  journal_rows: LiveJournalRow[];
  suggestions: Array<Record<string, unknown>>;
}> {
  const url = new URL("/api/journal/matching/relink-preview", API_BASE);
  url.searchParams.set("start", params.start);
  url.searchParams.set("end", params.end);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse(res);
}

export async function getMatchingLinks(params?: { start?: string; end?: string }): Promise<{
  ok: boolean;
  rows: Array<Record<string, unknown>>;
}> {
  const url = new URL("/api/journal/matching/links", API_BASE);
  if (params?.start) url.searchParams.set("start", params.start);
  if (params?.end) url.searchParams.set("end", params.end);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse(res);
}

export async function postMatchingUnlink(payload: {
  journal_id: string;
  trade_id?: string;
  trade_day?: string;
}): Promise<{ ok: boolean; inactivated: number }> {
  const url = new URL("/api/journal/matching/unlink", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    })
  );
  return handleResponse(res);
}

export async function postMatchingReconfirm(payload: {
  journal_id: string;
  trade_id?: string;
  trade_day?: string;
}): Promise<{ ok: boolean; updated: number }> {
  const url = new URL("/api/journal/matching/reconfirm", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    })
  );
  return handleResponse(res);
}

export async function getDataFetchStatus(): Promise<{
  ok: boolean;
  rows: Array<{
    symbol: string;
    data_path: string;
    exists: boolean;
    rows: number;
    last_date: string;
    status: string;
    error?: string;
  }>;
}> {
  const url = new URL("/api/data/fetch/status", API_BASE);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse(res);
}

export async function postDataFetchRun(payload?: { max_retries?: number; retry_delay?: number }): Promise<{
  ok: boolean;
  summary: Record<string, unknown>;
}> {
  const url = new URL("/api/data/fetch/run", API_BASE);
  const res = await fetch(
    url.toString(),
    withAuth({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload ?? {}),
    })
  );
  return handleResponse(res);
}
