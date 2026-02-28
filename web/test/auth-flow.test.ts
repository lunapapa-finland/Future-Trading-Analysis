import { describe, expect, it, beforeEach } from "vitest";
import { POST as loginPost } from "../app/api/auth/login/route";
import { proxy } from "../proxy";
import { createHmac } from "crypto";

function makeProxyRequest(pathname: string, cookieValue?: string) {
  const url = new URL(`http://localhost${pathname}`);
  return {
    nextUrl: {
      pathname: url.pathname,
      clone: () => new URL(url.toString())
    },
    cookies: {
      get: (name: string) => (name === "fta_session" && cookieValue ? { value: cookieValue } : undefined)
    }
  } as any;
}

function signedToken(secret: string, exp: number): string {
  const payload = {
    v: 1,
    sub: "test-user",
    iat: Math.floor(Date.now() / 1000),
    exp,
    n: "nonce"
  };
  const payloadB64 = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const sig = createHmac("sha256", secret).update(payloadB64).digest("hex");
  return `v1.${payloadB64}.${sig}`;
}

describe("auth flow", () => {
  beforeEach(() => {
    process.env.DASH_USER = "test-user";
    process.env.DASH_PASS = "test-pass";
    process.env.SESSION_SIGNING_KEY = "test-session-secret";
    process.env.SECRET_KEY = "fallback-secret";
  });

  it("rejects invalid login", async () => {
    const req = new Request("http://localhost/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "bad", password: "creds" })
    });
    const res = await loginPost(req);
    expect(res.status).toBe(401);
  });

  it("sets signed session cookie on successful login", async () => {
    const req = new Request("http://localhost/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "test-user", password: "test-pass" })
    });
    const res = await loginPost(req);
    expect(res.status).toBe(200);
    const setCookie = res.headers.get("set-cookie") || "";
    expect(setCookie).toContain("fta_session=v1.");
    expect(setCookie).toContain("HttpOnly");
  });

  it("redirects protected route to /login when no session exists", async () => {
    const res = await proxy(makeProxyRequest("/trading"));
    expect(res.status).toBe(307);
    expect(res.headers.get("location")).toBe("http://localhost/login");
  });

  it("allows protected route when session token is valid", async () => {
    const token = signedToken("test-session-secret", Math.floor(Date.now() / 1000) + 3600);
    const res = await proxy(makeProxyRequest("/analysis", token));
    expect(res.status).toBe(200);
    expect(res.headers.get("location")).toBeNull();
  });
});
