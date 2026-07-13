export function getSupabasePublicConfig() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim();

  if (!url || !publishableKey) {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY are required");
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(url);
  } catch {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL must be a valid absolute URL");
  }

  if (isProductionEnvironment()) {
    if (parsedUrl.protocol !== "https:" || isLocalHostname(parsedUrl.hostname)) {
      throw new Error("NEXT_PUBLIC_SUPABASE_URL must be a non-local HTTPS URL in production");
    }
    if (isPlaceholder(publishableKey)) {
      throw new Error("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY cannot be a placeholder in production");
    }
  }

  return { url, publishableKey } as const;
}

export function isProductionEnvironment(environment: NodeJS.ProcessEnv = process.env) {
  return environment.APP_ENV === "production";
}

function isLocalHostname(hostname: string) {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1";
}

function isPlaceholder(value: string) {
  return /placeholder|optional_until|replace_me|changeme|<[^>]+>/i.test(value);
}
