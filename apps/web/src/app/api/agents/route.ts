import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

function failure(error: unknown, fallback: string) {
  const status = error instanceof BigHeadApiError ? error.status : 500;
  return NextResponse.json({ detail: error instanceof Error ? error.message : fallback }, { status });
}

async function tenantId() {
  return (await getWorkspaceRequestContext()).tenantId ?? "";
}

function trustedOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const allowed = new Set([new URL(request.url).origin]);
  const appUrl = process.env.APP_URL?.trim();
  if (appUrl) try { allowed.add(new URL(appUrl).origin); } catch { /* invalid config is not trusted */ }
  return allowed.has(origin);
}

export async function GET() {
  const organizationId = await tenantId();
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  try {
    return NextResponse.json(await authenticatedApi<unknown>("/v1/agents", { organizationId }), { headers: { "cache-control": "no-store" } });
  } catch (error) { return failure(error, "Nao foi possivel carregar os agentes."); }
}

export async function POST(request: Request) {
  if (!trustedOrigin(request)) return NextResponse.json({ detail: "Origem nao autorizada." }, { status: 403 });
  const organizationId = await tenantId();
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const name = typeof body?.name === "string" ? body.name.trim() : "";
  const slug = typeof body?.slug === "string" ? body.slug.trim() : "";
  const prompt = typeof body?.prompt === "string" ? body.prompt.trim() : "";
  if (!name || name.length > 160 || slug.length > 160 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug) || !prompt) {
    return NextResponse.json({ detail: "Nome, slug e prompt validos sao obrigatorios." }, { status: 422 });
  }
  try {
    const agent = await authenticatedApi<unknown>("/v1/agents", {
      method: "POST", organizationId, headers: { "content-type": "application/json" },
      body: JSON.stringify({
        name, slug,
        description: typeof body?.description === "string" ? body.description.trim() || null : null,
        riskLevel: typeof body?.riskLevel === "string" ? body.riskLevel : "low",
        prompt,
        modelId: typeof body?.modelId === "string" && body.modelId ? body.modelId : null,
        limits: body?.limits && typeof body.limits === "object" && !Array.isArray(body.limits) ? body.limits : {},
        skillIds: Array.isArray(body?.skillIds) ? body.skillIds : []
      })
    });
    return NextResponse.json(agent, { status: 201 });
  } catch (error) { return failure(error, "Nao foi possivel criar o agente."); }
}
