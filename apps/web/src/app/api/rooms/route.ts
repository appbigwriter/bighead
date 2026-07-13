import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

async function tenantId() {
  return (await getWorkspaceRequestContext()).tenantId ?? "";
}

function failure(error: unknown) {
  const status = error instanceof BigHeadApiError ? error.status : 500;
  return NextResponse.json({ detail: error instanceof Error ? error.message : "Nao foi possivel carregar as salas." }, { status });
}

export async function GET() {
  const organizationId = await tenantId();
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  try {
    return NextResponse.json(await authenticatedApi<unknown>("/v1/rooms?limit=100", { organizationId }), { headers: { "cache-control": "no-store" } });
  } catch (error) { return failure(error); }
}

export async function POST(request: Request) {
  const organizationId = await tenantId();
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  const incoming = await request.json().catch(() => null) as { name?: unknown; description?: unknown; isPrivate?: unknown } | null;
  const name = typeof incoming?.name === "string" ? incoming.name.trim() : "";
  if (!name || name.length > 160) return NextResponse.json({ detail: "Informe um nome valido para a sala." }, { status: 422 });
  const description = typeof incoming?.description === "string" ? incoming.description.trim() || null : null;
  try {
    const room = await authenticatedApi<unknown>("/v1/rooms", {
      method: "POST", organizationId, headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, description, isPrivate: incoming?.isPrivate === true })
    });
    return NextResponse.json(room, { status: 201 });
  } catch (error) { return failure(error); }
}
