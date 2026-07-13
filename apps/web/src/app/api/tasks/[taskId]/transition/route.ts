import { NextResponse } from "next/server";

import { mutationFailure, type MutationResult } from "@/lib/mutation-result";
import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { isTaskStatus } from "@/lib/task-transitions";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function trustedOrigin(request: Request) {
  const origin = request.headers.get("origin");
  if (!origin) return false;
  const allowed = new Set([new URL(request.url).origin]);
  const appUrl = process.env.APP_URL?.trim();
  if (appUrl) {
    try { allowed.add(new URL(appUrl).origin); } catch { /* invalid deployment config is never trusted */ }
  }
  return allowed.has(origin);
}

function response(result: MutationResult) {
  return NextResponse.json(result, { status: result.status });
}

export async function POST(request: Request, context: { params: Promise<{ taskId: string }> }) {
  if (!trustedOrigin(request)) return response(mutationFailure(403));
  const organizationId = (await getWorkspaceRequestContext()).tenantId ?? "";
  const { taskId } = await context.params;
  if (!organizationId) return response(mutationFailure(400, "Tenant ativo obrigatorio."));
  if (!uuidPattern.test(taskId)) return response(mutationFailure(422, "Tarefa invalida."));

  const body = await request.json().catch(() => null) as Record<string, unknown> | null;
  const targetState = typeof body?.targetState === "string" ? body.targetState.trim() : "";
  const expectedVersion = body?.expectedVersion;
  const reason = body?.reason;
  if (!isTaskStatus(targetState) || targetState === "new" || !Number.isInteger(expectedVersion) || Number(expectedVersion) < 1) {
    return response(mutationFailure(422, "Transicao ou versao invalida."));
  }
  if (reason !== null && reason !== undefined && (typeof reason !== "string" || reason.length > 4_000)) {
    return response(mutationFailure(422, "Motivo invalido."));
  }

  try {
    const result = await authenticatedApi<{ task: { id: string; version: number; status: string } }>(
      `/v1/tasks/${encodeURIComponent(taskId)}/transition`,
      {
        method: "POST",
        organizationId,
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ targetState, expectedVersion, reason: reason || null })
      }
    );
    return response({
      ok: true,
      status: 200,
      message: `Tarefa movida para ${result.task.status}.`,
      data: { taskId: result.task.id, version: result.task.version, status: result.task.status }
    });
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return response(mutationFailure(status, error instanceof Error ? error.message : undefined));
  }
}
