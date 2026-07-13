import "server-only";

import { createClient } from "./supabase/server";

export class BigHeadApiError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

export async function getValidatedAccessToken() {
  const supabase = await createClient();
  const { data: claims, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claims?.claims) throw new BigHeadApiError(401, "Sessao invalida ou expirada");
  const { data, error } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (error || !token) throw new BigHeadApiError(401, "Sessao invalida ou expirada");
  return token;
}

export async function authenticatedApi<T>(
  path: string,
  options: RequestInit & { organizationId?: string } = {}
): Promise<T> {
  const token = await getValidatedAccessToken();
  return apiRequest<T>(path, {
    ...options,
    headers: {
      authorization: `Bearer ${token}`,
      ...(options.organizationId ? { "x-organization-id": options.organizationId } : {}),
      ...options.headers
    }
  });
}

export async function publicApi<T>(path: string, options: RequestInit = {}): Promise<T> {
  return apiRequest<T>(path, options);
}

async function apiRequest<T>(path: string, options: RequestInit): Promise<T> {
  const baseUrl = process.env.API_URL?.trim() || process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!baseUrl) throw new BigHeadApiError(500, "API_URL nao configurada");
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}${path}`, {
    ...options,
    cache: "no-store",
    headers: { accept: "application/json", ...options.headers }
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: unknown; title?: unknown } | null;
    const detail = typeof body?.detail === "string" ? body.detail : typeof body?.title === "string" ? body.title : response.statusText;
    throw new BigHeadApiError(response.status, detail || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}
