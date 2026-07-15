export function getSupabasePublicConfig(environment?: NodeJS.ProcessEnv) {
  const url = (
    environment?.SUPABASE_SERVER_URL ??
    environment?.NEXT_PUBLIC_SUPABASE_URL ??
    process.env.SUPABASE_SERVER_URL ??
    process.env.NEXT_PUBLIC_SUPABASE_URL
  )?.trim();
  const publishableKey = (
    environment?.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
  )?.trim();

  if (!url || !publishableKey) {
    throw new Error(
      "SUPABASE_SERVER_URL/NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY are required"
    );
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(url);
  } catch {
    throw new Error("NEXT_PUBLIC_SUPABASE_URL must be a valid absolute URL");
  }

  if (isProductionEnvironment(environment ?? process.env)) {
    if (
      parsedUrl.protocol !== "https:" ||
      isLocalHostname(parsedUrl.hostname)
    ) {
      throw new Error(
        "NEXT_PUBLIC_SUPABASE_URL must be a non-local HTTPS URL in production"
      );
    }
    if (isUnsafePublicKey(publishableKey)) {
      throw new Error(
        "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY must be a public anon/publishable key in production"
      );
    }
  }

  return { url, publishableKey } as const;
}

export function isProductionEnvironment(
  environment: NodeJS.ProcessEnv = process.env
) {
  const appProduction = environment.APP_ENV === "production";
  const nodeProduction = environment.NODE_ENV === "production";
  const insecureLocalProduction =
    nodeProduction &&
    environment.APP_ENV === "test" &&
    environment.ALLOW_INSECURE_LOCAL_PRODUCTION === "true";
  if (appProduction && !nodeProduction) {
    throw new Error("APP_ENV=production requires NODE_ENV=production");
  }
  if (
    nodeProduction &&
    environment.APP_ENV &&
    !["production", "staging"].includes(environment.APP_ENV) &&
    !insecureLocalProduction
  ) {
    throw new Error(
      "NODE_ENV=production requires APP_ENV=staging or production"
    );
  }
  return nodeProduction && !insecureLocalProduction;
}

function isLocalHostname(hostname: string) {
  return (
    hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1"
  );
}

function isUnsafePublicKey(value: string) {
  if (
    /placeholder|optional_until|replace_me|changeme|<[^>]+>|^sb_secret_/i.test(
      value
    )
  )
    return true;
  const parts = value.split(".");
  if (parts.length !== 3) return false;
  try {
    const payload = parts[1]!.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = JSON.parse(
      atob(payload.padEnd(Math.ceil(payload.length / 4) * 4, "="))
    ) as { role?: unknown };
    return decoded.role === "service_role" || decoded.role === "supabase_admin";
  } catch {
    return false;
  }
}
