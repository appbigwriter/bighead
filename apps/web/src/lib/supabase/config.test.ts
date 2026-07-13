import { describe, expect, it } from "vitest";

import { getSupabasePublicConfig, isProductionEnvironment } from "./config";

const base = {
  NODE_ENV: "production",
  APP_ENV: "production",
  NEXT_PUBLIC_SUPABASE_URL: "https://project.supabase.co",
  NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_public-test"
} as NodeJS.ProcessEnv;

describe("Supabase public production configuration", () => {
  it.each(["sb_secret_private", "placeholder", legacyJwt({ role: "service_role" }), legacyJwt({ role: "supabase_admin" })])(
    "rejects a privileged or placeholder public key",
    (key) => expect(() => getSupabasePublicConfig({ ...base, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: key })).toThrow("public anon/publishable")
  );

  it("accepts a legacy anon JWT", () => {
    expect(getSupabasePublicConfig({ ...base, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: legacyJwt({ role: "anon" }) }).url).toBe("https://project.supabase.co");
  });

  it("runs staging in hardened mode when Next runs in production mode", () => {
    expect(isProductionEnvironment({ APP_ENV: "staging", NODE_ENV: "production" })).toBe(true);
  });

  it("rejects APP_ENV=production outside the production Node runtime", () => {
    expect(() => isProductionEnvironment({ APP_ENV: "production", NODE_ENV: "test" })).toThrow("APP_ENV=production requires NODE_ENV=production");
  });

  it("rejects a development deployment running through the production Node server", () => {
    expect(() => isProductionEnvironment({ APP_ENV: "development", NODE_ENV: "production" })).toThrow("APP_ENV=staging or production");
  });
});

function legacyJwt(payload: object) {
  return `${btoa(JSON.stringify({ alg: "HS256" }))}.${btoa(JSON.stringify(payload))}.signature`;
}
