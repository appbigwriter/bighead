import { describe, expect, it } from "vitest";

import { readSupabaseAuthRuntimeConfig, safeInternalRedirect } from "./auth-config";

const production = {
  NODE_ENV: "production",
  APP_ENV: "production",
  APP_URL: "https://app.bighead.example",
  SUPABASE_AUTH_SITE_URL: "https://app.bighead.example",
  SUPABASE_AUTH_REDIRECT_URLS: "https://app.bighead.example/auth/callback",
  SUPABASE_AUTH_SMTP_CONFIGURED: "true"
} as NodeJS.ProcessEnv;

describe("readSupabaseAuthRuntimeConfig", () => {
  it("accepts an explicit production Auth configuration", () => {
    expect(readSupabaseAuthRuntimeConfig(production)).toMatchObject({ appUrl: "https://app.bighead.example", smtpConfigured: true });
  });

  it.each([
    [{ ...production, APP_URL: "http://localhost:3000" }, "non-local HTTPS"],
    [{ ...production, SUPABASE_AUTH_SITE_URL: "https://other.example" }, "same origin"],
    [{ ...production, SUPABASE_AUTH_REDIRECT_URLS: "https://app.bighead.example/other" }, "must include"],
    [{ ...production, SUPABASE_AUTH_SMTP_CONFIGURED: "false" }, "SMTP_CONFIGURED=true"]
  ])("fails closed for an unsafe production configuration", (environment, message) => {
    expect(() => readSupabaseAuthRuntimeConfig(environment as NodeJS.ProcessEnv)).toThrow(message);
  });
});

describe("safeInternalRedirect", () => {
  const appUrl = "https://app.bighead.example";

  it.each(["https://evil.example", "//evil.example", "/\\evil.example", "/ok\u0000evil", "/ok%0devil"])("rejects hostile redirect %s", (value) => {
    expect(safeInternalRedirect(value, appUrl)).toBe("/operacao/home");
  });

  it("allows an internal path", () => {
    expect(safeInternalRedirect("/auth/update-password?verified=1", appUrl)).toBe("/auth/update-password?verified=1");
  });
});
