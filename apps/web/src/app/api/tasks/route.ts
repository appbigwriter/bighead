import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { isTaskStatus } from "@/lib/task-transitions";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

function trustedOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const allowed = new Set([new URL(request.url).origin]);
  const appUrl = process.env.APP_URL?.trim();
  if (appUrl) { try { allowed.add(new URL(appUrl).origin); } catch { /* never trust invalid configuration */ } }
  return allowed.has(origin);
}

function failure(error: unknown) {
  const status = error instanceof BigHeadApiError ? error.status : 500;
  return NextResponse.json({ detail: error instanceof Error ? error.message : "Operacao nao concluida." }, { status });
}

export async function GET(request: Request) {
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  const searchParams = new URL(request.url).searchParams;
  const requestedStatus = searchParams.get("status")?.trim() || "";
  if (requestedStatus && !isTaskStatus(requestedStatus)) return NextResponse.json({ detail: "Filtro de estado invalido." }, { status: 422 });
  const query = new URLSearchParams({ limit: "100" });
  if (requestedStatus) query.set("status", requestedStatus);
  for (const name of ["ownerId", "assigneeId", "risk", "slaStatus", "roomId"] as const) {
    const value = searchParams.get(name)?.trim();
    if (value) query.set(name, value);
  }
  try {
    return NextResponse.json(await authenticatedApi<unknown>(`/v1/tasks?${query.toString()}`, { organizationId }), { headers: { "cache-control": "no-store" } });
  } catch (error) { return failure(error); }
}

export async function POST(request: Request) {
  if (!trustedOrigin(request)) return NextResponse.json({ detail: "Origem nao autorizada." }, { status: 403 });
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  const key = request.headers.get("idempotency-key")?.trim() ?? "";
  if (!key || key.length > 200) return NextResponse.json({ detail: "Chave de envio invalida." }, { status: 422 });
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const goal = typeof body?.goal === "string" ? body.goal.trim() : "";
  if (!goal || goal.length > 10_000) return NextResponse.json({ detail: "Informe um objetivo valido." }, { status: 422 });
  const payload = {
    goal,
    title: typeof body?.title === "string" ? body.title.trim() || null : null,
    risk: typeof body?.risk === "string" ? body.risk : "low",
    assigneeId: typeof body?.assigneeId === "string" ? body.assigneeId.trim() || null : null,
    roomId: typeof body?.roomId === "string" ? body.roomId || null : null,
    sourceMessageId: typeof body?.sourceMessageId === "string" ? body.sourceMessageId || null : null,
    slaAt: typeof body?.slaAt === "string" ? body.slaAt || null : null,
    dependencies: Array.isArray(body?.dependencies) ? body.dependencies.filter((item): item is string => typeof item === "string") : []
  };
  try {
    const result = await authenticatedApi<unknown>("/v1/tasks", {
      method: "POST", organizationId,
      headers: { "content-type": "application/json", "Idempotency-Key": key },
      body: JSON.stringify(payload)
    });
    return NextResponse.json(result, { status: 201 });
  } catch (error) { return failure(error); }
}
