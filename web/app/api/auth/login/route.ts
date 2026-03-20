import { NextResponse } from "next/server";
import { createHmac, randomBytes } from "crypto";

const SESSION_COOKIE = "fta_session";

function isHttpsRequest(request: Request): boolean {
  const forwardedProto = request.headers.get("x-forwarded-proto");
  if (forwardedProto) {
    return forwardedProto.split(",")[0].trim().toLowerCase() === "https";
  }
  try {
    return new URL(request.url).protocol === "https:";
  } catch {
    return false;
  }
}

function getSessionSecret(): string | null {
  return process.env.SESSION_SIGNING_KEY || process.env.SECRET_KEY || null;
}

function createSessionToken(username: string, secret: string): string {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    v: 1,
    sub: username,
    iat: now,
    n: randomBytes(8).toString("hex")
  };
  const payloadB64 = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const sig = createHmac("sha256", secret).update(payloadB64).digest("hex");
  return `v1.${payloadB64}.${sig}`;
}

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  const { username, password } = body as { username?: string; password?: string };

  const expectedUser = process.env.DASH_USER;
  const expectedPass = process.env.DASH_PASS;

  if (!expectedUser || !expectedPass) {
    return NextResponse.json({ message: "Credentials not configured" }, { status: 500 });
  }

  if (username !== expectedUser || password !== expectedPass) {
    return NextResponse.json({ message: "Invalid username or password" }, { status: 401 });
  }

  const sessionSecret = getSessionSecret();
  if (!sessionSecret) {
    return NextResponse.json({ message: "Session signing secret not configured" }, { status: 500 });
  }
  const sessionToken = createSessionToken(username, sessionSecret);
  const secureCookie = isHttpsRequest(request);

  const res = NextResponse.json({ ok: true });
  res.cookies.set({
    name: SESSION_COOKIE,
    value: sessionToken,
    httpOnly: true,
    sameSite: "lax",
    secure: secureCookie,
    path: "/",
  });
  return res;
}
