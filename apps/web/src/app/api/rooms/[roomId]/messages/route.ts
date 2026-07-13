import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

function scalar(value: unknown, fallback: string) {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

export async function GET(_request: Request, context: { params: Promise<{ roomId: string }> }) {
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  const { roomId } = await context.params;
  if (!organizationId || !roomId) return NextResponse.json({ detail: "tenant ativo e sala sao obrigatorios" }, { status: 400 });
  try {
    const page = await authenticatedApi<{ messages: Array<Record<string, unknown>> }>(
      `/v1/rooms/${encodeURIComponent(roomId)}/messages`,
      { organizationId }
    );
    return NextResponse.json({
      messages: page.messages.map((message) => {
        const metadata = message.metadata && typeof message.metadata === "object" && !Array.isArray(message.metadata)
          ? message.metadata as Record<string, unknown>
          : {};
        const clientId = metadata.client_id ?? metadata.clientId;
        return {
          id: scalar(message.id, ""),
          roomId: scalar(message.roomId ?? message.room_id, roomId),
          ...(typeof clientId === "string" ? { clientId } : {}),
          body: scalar(message.body, ""),
          createdAt: scalar(message.createdAt ?? message.created_at, "")
        };
      })
    });
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Falha ao carregar mensagens" }, { status });
  }
}
