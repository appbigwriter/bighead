import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
function trustedOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const allowed = new Set([new URL(request.url).origin]);
  const appUrl = process.env.APP_URL?.trim();
  if (appUrl) { try { allowed.add(new URL(appUrl).origin); } catch { /* invalid config is not trusted */ } }
  return allowed.has(origin);
}

export async function POST(request: Request, context: { params: Promise<{ leadId: string }> }) {
  if (!trustedOrigin(request)) return NextResponse.json({ detail: "Origem nao autorizada." }, { status: 403 });
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  const { leadId } = await context.params;
  const key = request.headers.get("idempotency-key")?.trim() ?? "";
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  if (!uuid.test(leadId) || !key || key.length > 200) return NextResponse.json({ detail: "Envio invalido." }, { status: 422 });
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const action = typeof body?.action === "string" ? body.action.trim() : "";
  const dueAt = typeof body?.dueAt === "string" ? body.dueAt : "";
  const due = new Date(dueAt);
  const notes = typeof body?.notes === "string" ? body.notes.trim() : "";
  if (!action || action.length > 2000 || Number.isNaN(due.getTime()) || notes.length > 10_000) return NextResponse.json({ detail: "Informe acao e prazo validos." }, { status: 422 });
  try {
    const result = await authenticatedApi<unknown>(`/v1/crm/leads/${encodeURIComponent(leadId)}/follow-ups`, {
      method: "POST", organizationId,
      headers: { "content-type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify({ action, dueAt: due.toISOString(), notes: notes || null })
    });
    return NextResponse.json(result, { status: 201 });
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Nao foi possivel criar o follow-up." }, { status });
  }
}
