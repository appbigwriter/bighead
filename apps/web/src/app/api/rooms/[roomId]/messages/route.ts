import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

function scalar(value: unknown, fallback: string) {
  return typeof value === "string" || typeof value === "number" ? String(value) : fallback;
}

function messageView(message: Record<string, unknown>, roomId: string) {
  const metadata = message.metadata && typeof message.metadata === "object" && !Array.isArray(message.metadata)
    ? message.metadata as Record<string, unknown>
    : {};
  const clientId = metadata.client_id ?? metadata.clientId;
  return {
    id: scalar(message.id, ""),
    roomId: scalar(message.roomId ?? message.room_id, roomId),
    ...(typeof clientId === "string" ? { clientId } : {}),
    ...(typeof (message.authorUserId ?? message.author_user_id) === "string" ? { authorUserId: String(message.authorUserId ?? message.author_user_id) } : {}),
    body: scalar(message.body, ""),
    metadata,
    ...(typeof (message.editedAt ?? message.edited_at) === "string" ? { editedAt: String(message.editedAt ?? message.edited_at) } : {}),
    ...(typeof (message.deletedAt ?? message.deleted_at) === "string" ? { deletedAt: String(message.deletedAt ?? message.deleted_at) } : {}),
    createdAt: scalar(message.createdAt ?? message.created_at, "")
  };
}

export async function GET(_request: Request, context: { params: Promise<{ roomId: string }> }) {
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  const { roomId } = await context.params;
  if (!organizationId || !roomId) return NextResponse.json({ detail: "tenant ativo e sala sao obrigatorios" }, { status: 400 });
  try {
    const page = await authenticatedApi<{ messages: Array<Record<string, unknown>>; roomContext?: unknown; nextCursor?: unknown }>(
      `/v1/rooms/${encodeURIComponent(roomId)}/messages`,
      { organizationId }
    );
    return NextResponse.json({
      messages: page.messages.map((message) => messageView(message, roomId)),
      roomContext: page.roomContext ?? null,
      nextCursor: page.nextCursor ?? null
    });
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Falha ao carregar mensagens" }, { status });
  }
}

export async function POST(request: Request, context: { params: Promise<{ roomId: string }> }) {
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  const { roomId } = await context.params;
  const incoming = await request.json().catch(() => null) as { body?: unknown; clientId?: unknown } | null;
  const body = typeof incoming?.body === "string" ? incoming.body.trim() : "";
  const clientId = typeof incoming?.clientId === "string" ? incoming.clientId.trim() : "";
  if (!organizationId || !roomId) return NextResponse.json({ detail: "Sala indisponivel." }, { status: 400 });
  if (!body || body.length > 100_000 || !clientId || clientId.length > 120) return NextResponse.json({ detail: "Mensagem invalida." }, { status: 422 });
  try {
    const message = await authenticatedApi<Record<string, unknown>>(`/v1/rooms/${encodeURIComponent(roomId)}/messages`, {
      method: "POST", organizationId, headers: { "content-type": "application/json" }, body: JSON.stringify({ body, clientId })
    });
    return NextResponse.json(messageView(message, roomId), { status: 201 });
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Nao foi possivel enviar a mensagem." }, { status });
  }
}
