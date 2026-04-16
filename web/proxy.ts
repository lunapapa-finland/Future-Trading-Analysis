import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const SESSION_COOKIE = "fta_session";
const PROTECTED_PATHS = ["/guide", "/live", "/upload", "/matching", "/trading", "/analysis", "/portfolio", "/config"];

const encoder = new TextEncoder();

function hex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function signHmacSHA256(message: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, encoder.encode(message));
  return hex(sig);
}

function decodePayload(payloadB64: string): Record<string, unknown> | null {
  try {
    const normalized = payloadB64.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
    const json = atob(padded);
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function getSessionTtlSeconds(): number {
  const raw = process.env.SESSION_TTL_SECONDS || "43200";
  const n = Number.parseInt(raw, 10);
  if (!Number.isFinite(n)) return 43_200;
  return Math.max(300, n);
}

function isPayloadCurrent(payload: Record<string, unknown>): boolean {
  const now = Math.floor(Date.now() / 1000);
  const expRaw = payload.exp;
  if (expRaw !== undefined) {
    const exp = Number(expRaw);
    return Number.isFinite(exp) && exp > now;
  }
  const iat = Number(payload.iat);
  if (!Number.isFinite(iat)) return false;
  return iat + getSessionTtlSeconds() > now;
}

async function hasValidSessionToken(rawToken: string | undefined): Promise<boolean> {
  if (!rawToken) return false;
  const parts = rawToken.split(".");
  if (parts.length !== 3 || parts[0] !== "v1") return false;
  const payloadB64 = parts[1];
  const sig = parts[2];
  const secret = process.env.SESSION_SIGNING_KEY || process.env.SECRET_KEY;
  if (!secret) return false;
  const expectedSig = await signHmacSHA256(payloadB64, secret);
  if (sig !== expectedSig) return false;
  const payload = decodePayload(payloadB64);
  if (!payload) return false;
  return isPayloadCurrent(payload);
}

export async function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (pathname.startsWith("/api") || pathname.startsWith("/login")) {
    return NextResponse.next();
  }

  const isProtected = PROTECTED_PATHS.some((path) => pathname.startsWith(path));
  if (!isProtected) return NextResponse.next();

  const session = request.cookies.get(SESSION_COOKIE)?.value;
  if (await hasValidSessionToken(session)) return NextResponse.next();

  const url = request.nextUrl.clone();
  url.pathname = "/login";
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"]
};
