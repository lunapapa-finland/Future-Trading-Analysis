import { AnalysisPayload, AnalysisSeriesPoint, Candle, PerformanceRecord } from "./types";
import type { TradingSession } from "./types";

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
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text || res.statusText}`);
  }
  return res.json() as Promise<T>;
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

export async function postAnalysis(metric: string, payload: AnalysisPayload): Promise<AnalysisSeriesPoint[]> {
  const url = new URL(`/api/analysis/${metric}`, API_BASE);
  const res = await fetch(url.toString(), withAuth({
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {})
  }));
  return handleResponse<AnalysisSeriesPoint[]>(res);
}

export async function getTradingSession(params: { symbol: string; start?: string; end?: string }): Promise<TradingSession> {
  const url = new URL("/api/trading/session", API_BASE);
  url.searchParams.set("symbol", params.symbol);
  if (params.start) url.searchParams.set("start", params.start);
  if (params.end) url.searchParams.set("end", params.end);
  const res = await fetch(url.toString(), withAuth({ cache: "no-store" }));
  return handleResponse<TradingSession>(res);
}
