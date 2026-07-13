import { NextResponse } from "next/server";
import { describe, expect, it } from "vitest";

import { authCookieOptions, protectedAuthCookieOptions } from "./cookie-options";

describe("Supabase auth cookie policy", () => {
  it("serializes production login/refresh cookies with hardened flags", () => {
    const response = NextResponse.next();
    response.cookies.set("sb-session", "token", authCookieOptions("production"));
    const header = response.headers.get("set-cookie") ?? "";
    expect(header).toContain("HttpOnly"); expect(header).toContain("Secure");
    expect(header).toContain("SameSite=lax"); expect(header).toContain("Path=/");
  });

  it("keeps logout expiry while enforcing the same cookie boundary", () => {
    expect(protectedAuthCookieOptions({ maxAge: 0 }, "production")).toMatchObject({ maxAge: 0, httpOnly: true, secure: true, sameSite: "lax", path: "/" });
    expect(authCookieOptions("development").secure).toBe(false);
  });

  it("derives Secure from the canonical URL for local HTTP and hosted HTTPS", () => {
    expect(authCookieOptions({ APP_URL: "http://127.0.0.1:3101", APP_ENV: "test", NODE_ENV: "production" }).secure).toBe(false);
    expect(authCookieOptions({ APP_URL: "https://app.bighead.example", APP_ENV: "production", NODE_ENV: "production" }).secure).toBe(true);
  });
});
