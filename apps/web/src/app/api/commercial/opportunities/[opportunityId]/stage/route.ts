import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const stages = new Set(["discovery", "qualification", "proposal", "negotiation", "won", "lost"]);
function trustedOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const allowed = new Set([new URL(request.url).origin]);
  const appUrl = process.env.APP_URL?.trim();
  if (appUrl) { try { allowed.add(new URL(appUrl).origin); } catch { /* invalid config is not trusted */ } }
  return allowed.has(origin);
}

export async function POST(request: Request, context: { params: Promise<{ opportunityId: string }> }) {
  if (!trustedOrigin(request)) return NextResponse.json({ detail: "Origem nao autorizada." }, { status: 403 });
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  const { opportunityId } = await context.params;
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  if (!uuid.test(opportunityId)) return NextResponse.json({ detail: "Oportunidade invalida." }, { status: 422 });
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const targetStage = typeof body?.targetStage === "string" ? body.targetStage : "";
  const amount = body?.amount === "" || body?.amount == null ? null : Number(body.amount);
  const probability = body?.probability === "" || body?.probability == null ? null : Number(body.probability);
  const expectedCloseDate = typeof body?.expectedCloseDate === "string" ? body.expectedCloseDate || null : null;
  const lossReason = typeof body?.lossReason === "string" ? body.lossReason.trim() || null : null;
  if (!stages.has(targetStage) || (amount !== null && (!Number.isFinite(amount) || amount <= 0)) || (probability !== null && (!Number.isFinite(probability) || probability < 0 || probability > 100))) {
    return NextResponse.json({ detail: "Etapa ou previsao invalida." }, { status: 422 });
  }
  try {
    return NextResponse.json(await authenticatedApi<unknown>(`/v1/crm/opportunities/${encodeURIComponent(opportunityId)}/stage`, {
      method: "POST", organizationId, headers: { "content-type": "application/json" },
      body: JSON.stringify({ targetStage, amount, probability, expectedCloseDate, lossReason, requiredFields: {}, forecast: {} })
    }));
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Nao foi possivel mover a oportunidade." }, { status });
  }
}
