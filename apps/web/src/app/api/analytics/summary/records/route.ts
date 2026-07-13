import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

export async function GET(request: Request) {
  const incoming = new URL(request.url).searchParams;
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  const dimension = incoming.get("dimension") ?? "";
  if (!organizationId || !dimension) return NextResponse.json({ detail: "tenant ativo e dimension sao obrigatorios" }, { status: 400 });
  const query = new URLSearchParams({ dimension, limit: incoming.get("limit") ?? "100" });
  for (const key of ["from", "to", "cursor"] as const) {
    const value = incoming.get(key);
    if (value) query.set(key, value);
  }
  try {
    const page = await authenticatedApi<unknown>(`/v1/analytics/summary/records?${query.toString()}`, { organizationId });
    return NextResponse.json(page);
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Falha ao carregar registros" }, { status });
  }
}
