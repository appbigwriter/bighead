import type { CookieOptions } from "@supabase/ssr";

type CookieEnvironment = string | Partial<Pick<NodeJS.ProcessEnv, "APP_URL" | "APP_ENV" | "NODE_ENV">>;

function requiresSecureCookie(environment: CookieEnvironment) {
  if (typeof environment === "string") return environment === "production";
  if (environment.APP_URL) {
    try { return new URL(environment.APP_URL).protocol === "https:"; } catch { return true; }
  }
  return environment.APP_ENV === "production" || environment.APP_ENV === "staging" || environment.NODE_ENV === "production";
}

export function authCookieOptions(environment: CookieEnvironment = process.env): CookieOptions {
  return { httpOnly: true, secure: requiresSecureCookie(environment), sameSite: "lax", path: "/" };
}

export function protectedAuthCookieOptions(options: CookieOptions, environment: CookieEnvironment = process.env): CookieOptions {
  return { ...options, ...authCookieOptions(environment) };
}
