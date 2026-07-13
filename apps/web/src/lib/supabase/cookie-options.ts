import type { CookieOptions } from "@supabase/ssr";

export function authCookieOptions(environment = process.env.NODE_ENV): CookieOptions {
  return { httpOnly: true, secure: environment === "production", sameSite: "lax", path: "/" };
}

export function protectedAuthCookieOptions(options: CookieOptions, environment = process.env.NODE_ENV): CookieOptions {
  return { ...options, ...authCookieOptions(environment) };
}
