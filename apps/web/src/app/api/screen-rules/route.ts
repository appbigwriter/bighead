import { NextResponse } from "next/server";

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { getWorkspaceRequestContext } from "@/lib/workspace-request-context";
import { shouldUseMockWorkspace } from "@/lib/workspace-mode";

type ScreenRuleCommand = {
  code: string;
  operation: string;
  payload: Record<string, string | number | boolean>;
};

function commandFrom(value: unknown): ScreenRuleCommand | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const body = value as Record<string, unknown>;
  if (typeof body.code !== "string" || !/^T\d{2}$/.test(body.code)) return null;
  if (typeof body.operation !== "string" || body.operation.length === 0) return null;
  if (!body.payload || typeof body.payload !== "object" || Array.isArray(body.payload)) return null;
  return body as ScreenRuleCommand;
}

export async function POST(request: Request) {
  const command = commandFrom(await request.json().catch(() => null));
  if (!command) return NextResponse.json({ message: "Comando invalido." }, { status: 422 });
  if (shouldUseMockWorkspace()) {
    return NextResponse.json({ message: "Operacao aceita pela fronteira mock." });
  }
  const organizationId = (await getWorkspaceRequestContext()).tenantId;
  if (!organizationId) return NextResponse.json({ message: "Nenhuma organizacao ativa." }, { status: 400 });
  try {
    return NextResponse.json(await authenticatedApi<unknown>("/v1/screen-rules", {
      method: "POST",
      organizationId,
      headers: { "content-type": "application/json" },
      body: JSON.stringify(command)
    }));
  } catch (error) {
    const status = error instanceof BigHeadApiError ? error.status : 500;
    return NextResponse.json({ message: error instanceof Error ? error.message : "Operacao indisponivel." }, { status });
  }
}
