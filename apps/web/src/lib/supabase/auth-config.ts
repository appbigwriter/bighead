import { isProductionEnvironment } from "./config";

export type SupabaseAuthRuntimeConfig = {
  appUrl: string;
  siteUrl: string;
  redirectUrls: readonly string[];
  smtpConfigured: boolean;
};

export function readSupabaseAuthRuntimeConfig(environment: NodeJS.ProcessEnv = process.env): SupabaseAuthRuntimeConfig {
  const production = isProductionEnvironment(environment);
  const appUrl = normalizeUrl(environment.APP_URL ?? (production ? undefined : "http://localhost:3000"), "APP_URL");
  const siteUrl = normalizeUrl(environment.SUPABASE_AUTH_SITE_URL ?? (production ? undefined : appUrl), "SUPABASE_AUTH_SITE_URL");
  const redirectUrls = (environment.SUPABASE_AUTH_REDIRECT_URLS ?? (production ? "" : `${appUrl}/auth/callback`))
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean)
    .map((value) => normalizeUrl(value, "SUPABASE_AUTH_REDIRECT_URLS"));
  const smtpConfigured = environment.SUPABASE_AUTH_SMTP_CONFIGURED === "true";

  if (production) {
    assertProductionUrl(appUrl, "APP_URL");
    assertProductionUrl(siteUrl, "SUPABASE_AUTH_SITE_URL");
    if (new URL(appUrl).origin !== new URL(siteUrl).origin) {
      throw new Error("SUPABASE_AUTH_SITE_URL must use the same origin as APP_URL in production");
    }
    const callbackUrl = `${appUrl}/auth/callback`;
    if (!redirectUrls.includes(callbackUrl)) {
      throw new Error(`SUPABASE_AUTH_REDIRECT_URLS must include ${callbackUrl}`);
    }
    if (!smtpConfigured) {
      throw new Error("SUPABASE_AUTH_SMTP_CONFIGURED=true is required in production");
    }
  }

  return { appUrl, siteUrl, redirectUrls, smtpConfigured };
}

export function safeInternalRedirect(value: string | null, appUrl: string, fallback = "/operacao/home") {
  if (!value || hasControlCharacter(value) || /%(?:0[0-9a-f]|1[0-9a-f]|7f)/i.test(value)) return fallback;
  try {
    const base = new URL(appUrl);
    const resolved = new URL(value, base);
    if (resolved.origin !== base.origin || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) return fallback;
    return `${resolved.pathname}${resolved.search}${resolved.hash}`;
  } catch {
    return fallback;
  }
}

function hasControlCharacter(value: string) {
  return [...value].some((character) => {
    const code = character.charCodeAt(0);
    return code <= 31 || code === 127;
  });
}

function normalizeUrl(value: string | undefined, name: string) {
  if (!value?.trim()) throw new Error(`${name} is required`);
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    throw new Error(`${name} must contain valid absolute URLs`);
  }
  return url.toString().replace(/\/$/, "");
}

function assertProductionUrl(value: string, name: string) {
  const url = new URL(value);
  if (url.protocol !== "https:" || ["localhost", "127.0.0.1", "::1"].includes(url.hostname)) {
    throw new Error(`${name} must be a non-local HTTPS URL in production`);
  }
}
