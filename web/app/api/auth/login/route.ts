import { NextResponse } from "next/server";

const SESSION_COOKIE = "fta_session";
const SESSION_TTL = 60 * 60 * 24; // 1 day

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

  const res = NextResponse.json({ ok: true });
  res.cookies.set({
    name: SESSION_COOKIE,
    value: "ok",
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_TTL
  });
  return res;
}
