import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

function failure(error: unknown) {
  const status = error instanceof BigHeadApiError ? error.status : 500;
  return NextResponse.json({ detail: error instanceof Error ? error.message : "Nao foi possivel carregar os leads." }, { status });
}

export async function GET(request: Request) {
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  const input = new URL(request.url).searchParams;
  const query = new URLSearchParams({ limit: "100" });
  for (const name of ["stage", "ownerId"] as const) {
    const value = input.get(name)?.trim();
    if (value) query.set(name, value);
  }
  try {
    return NextResponse.json(await authenticatedApi<unknown>(`/v1/crm/leads?${query}`, { organizationId }), { headers: { "cache-control": "no-store" } });
  } catch (error) { return failure(error); }
}
