import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const decisions = new Set(["approved", "changes_requested", "rejected"]);

function trustedOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const allowed = new Set([new URL(request.url).origin]);
  const appUrl = process.env.APP_URL?.trim();
  if (appUrl) { try { allowed.add(new URL(appUrl).origin); } catch { /* invalid config is never trusted */ } }
  return allowed.has(origin);
}

export async function POST(request: Request, context: { params: Promise<{ approvalId: string }> }) {
  if (!trustedOrigin(request)) return NextResponse.json({ detail: "Origem nao autorizada." }, { status: 403 });
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  const { approvalId } = await context.params;
  if (!organizationId) return NextResponse.json({ detail: "Nenhuma organizacao ativa." }, { status: 400 });
  if (!uuidPattern.test(approvalId)) return NextResponse.json({ detail: "Aprovacao invalida." }, { status: 422 });
  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const decision = typeof body?.decision === "string" ? body.decision : "";
  const expectedRound = body?.expectedRound;
  const comment = typeof body?.comment === "string" ? body.comment.trim() : "";
  if (!decisions.has(decision) || !Number.isInteger(expectedRound) || Number(expectedRound) < 1 || comment.length > 10_000) {
    return NextResponse.json({ detail: "Decisao invalida." }, { status: 422 });
  }
  try {
    const result = await authenticatedApi<unknown>(`/v1/approvals/${encodeURIComponent(approvalId)}/decision`, {
      method: "POST", organizationId, headers: { "content-type": "application/json" },
      body: JSON.stringify({ decision, expectedRound, comment: comment || null })
    });
    return NextResponse.json(result);
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return NextResponse.json({ detail: error instanceof Error ? error.message : "Decisao nao registrada." }, { status });
  }
}
