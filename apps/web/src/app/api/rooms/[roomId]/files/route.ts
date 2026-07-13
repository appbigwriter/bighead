import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

export async function GET(_request: Request, context: { params: Promise<{ roomId: string }> }) {
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  const { roomId } = await context.params;
  if (!organizationId || !roomId) return NextResponse.json({ detail: "Sala indisponivel." }, { status: 400 });
  try {
    return NextResponse.json(await authenticatedApi<unknown>(`/v1/rooms/${encodeURIComponent(roomId)}/files?limit=50`, { organizationId }), { headers: { "cache-control": "no-store" } });
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Nao foi possivel carregar os arquivos." }, { status });
  }
}
