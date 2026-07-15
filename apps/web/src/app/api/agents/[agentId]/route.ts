import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function failure(error: unknown, fallback: string) {
  const status = error instanceof BigHeadApiError ? error.status : 500;
  return NextResponse.json({ detail: error instanceof Error ? error.message : fallback }, { status });
}

function trustedOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const allowed = new Set([new URL(request.url).origin]);
  const appUrl = process.env.APP_URL?.trim();
  if (appUrl) try { allowed.add(new URL(appUrl).origin); } catch { /* invalid config is not trusted */ }
  return allowed.has(origin);
}

async function context(agentId: string) {
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  if (!organizationId) return { error: NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 }) };
  if (!uuid.test(agentId)) return { error: NextResponse.json({ detail: "Agente invalido." }, { status: 422 }) };
  return { organizationId };
}

export async function GET(_request: Request, route: { params: Promise<{ agentId: string }> }) {
  const { agentId } = await route.params;
  const resolved = await context(agentId);
  if ("error" in resolved) return resolved.error;
  try {
    return NextResponse.json(await authenticatedApi<unknown>(`/v1/agents/${encodeURIComponent(agentId)}`, { organizationId: resolved.organizationId }), { headers: { "cache-control": "no-store" } });
  } catch (error) { return failure(error, "Nao foi possivel carregar o agente."); }
}

export async function PATCH(request: Request, route: { params: Promise<{ agentId: string }> }) {
  if (!trustedOrigin(request)) return NextResponse.json({ detail: "Origem nao autorizada." }, { status: 403 });
  const { agentId } = await route.params;
  const resolved = await context(agentId);
  if ("error" in resolved) return resolved.error;
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const expectedVersion = Number(body?.expectedVersion);
  if (!Number.isInteger(body?.expectedVersion) || expectedVersion < 0) {
    return NextResponse.json({ detail: "Versao esperada invalida." }, { status: 422 });
  }
  const prompt = typeof body?.prompt === "string" ? body.prompt.trim() : undefined;
  if (prompt !== undefined && !prompt) return NextResponse.json({ detail: "Prompt invalido." }, { status: 422 });
  try {
    return NextResponse.json(await authenticatedApi<unknown>(`/v1/agents/${encodeURIComponent(agentId)}`, {
      method: "PATCH", organizationId: resolved.organizationId, headers: { "content-type": "application/json" },
      body: JSON.stringify({
        name: typeof body?.name === "string" ? body.name.trim() || null : null,
        description: typeof body?.description === "string" ? body.description.trim() || null : null,
        riskLevel: typeof body?.riskLevel === "string" ? body.riskLevel : null,
        isEnabled: typeof body?.isEnabled === "boolean" ? body.isEnabled : null,
        ...(prompt === undefined ? {} : { prompt }),
        modelId: typeof body?.modelId === "string" && body.modelId ? body.modelId : null,
        limits: body?.limits && typeof body.limits === "object" && !Array.isArray(body.limits) ? body.limits : {},
        skillIds: Array.isArray(body?.skillIds) ? body.skillIds : [],
        expectedVersion
      })
    }));
  } catch (error) { return failure(error, "Nao foi possivel atualizar o agente."); }
}

export async function DELETE(request: Request, route: { params: Promise<{ agentId: string }> }) {
  if (!trustedOrigin(request)) return NextResponse.json({ detail: "Origem nao autorizada." }, { status: 403 });
  const { agentId } = await route.params;
  const resolved = await context(agentId);
  if ("error" in resolved) return resolved.error;
  const expectedVersion = Number(new URL(request.url).searchParams.get("expectedVersion"));
  if (!Number.isInteger(expectedVersion) || expectedVersion < 1) return NextResponse.json({ detail: "Versao esperada invalida." }, { status: 422 });
  try {
    await authenticatedApi<unknown>(`/v1/agents/${encodeURIComponent(agentId)}?expectedVersion=${expectedVersion}`, { method: "DELETE", organizationId: resolved.organizationId });
    return new NextResponse(null, { status: 204 });
  } catch (error) { return failure(error, "Nao foi possivel arquivar o agente."); }
}
