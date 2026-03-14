import { AnalysisPayload, AnalysisResponse, Candle, InsightsPayload, InsightsResponse, PerformanceRecord } from "./types";
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
    const msg = payload?.error || payload?.message || text || res.statusText;
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
