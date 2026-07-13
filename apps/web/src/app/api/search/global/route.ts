import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

const allowedScopes = new Set(["rooms", "messages", "tasks"]);

export async function POST(request: Request) {
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });

  const incoming = await request.json().catch(() => null) as { query?: unknown; scopes?: unknown } | null;
  const query = typeof incoming?.query === "string" ? incoming.query.trim() : "";
  const scopes = Array.isArray(incoming?.scopes)
    ? incoming.scopes.filter((scope): scope is string => typeof scope === "string" && allowedScopes.has(scope))
    : [];
  if (query.length < 2 || query.length > 200 || scopes.length === 0) {
    return NextResponse.json({ detail: "Informe ao menos dois caracteres e uma categoria." }, { status: 422 });
  }

  try {
    const response = await authenticatedApi<unknown>("/v1/search/global", {
      method: "POST",
      organizationId,
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ query, scopes, limit: 24 })
    });
    return NextResponse.json(response, { headers: { "cache-control": "no-store" } });
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    const detail = status === 403
      ? "Voce nao tem acesso a estes resultados."
      : error instanceof Error ? error.message : "Nao foi possivel concluir a busca.";
    return NextResponse.json({ detail }, { status });
  }
}
