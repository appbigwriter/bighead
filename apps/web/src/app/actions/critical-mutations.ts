"use server";

import { randomUUID } from "node:crypto";
import { cookies } from "next/headers";
import { revalidatePath } from "next/cache";

import { authenticatedApi, publicApi } from "@/lib/server-api-client";
import { shouldUseMockWorkspace } from "@/lib/workspace-mode";
import { authCookieOptions } from "@/lib/supabase/cookie-options";
import { mutationResultFromError } from "./mutation-error";
import type { MutationResult } from "@/lib/mutation-result";

export type { MutationResult } from "@/lib/mutation-result";

function text(form: FormData, name: string) {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function result(error: unknown): MutationResult {
  return mutationResultFromError(error);
}

export async function switchTenant(form: FormData): Promise<MutationResult> {
  try {
    const organizationId = text(form, "organizationId");
    const switched = await authenticatedApi<{ organizationId: string }>(`/v1/organizations/${encodeURIComponent(organizationId)}/switch`, { method: "POST" });
    if (switched.organizationId !== organizationId) return { ok: false, status: 403, message: "Organizacao indisponivel para esta conta." };
    const store = await cookies();
    store.set("bighead-organization-id", organizationId, { httpOnly: true, sameSite: "lax", secure: authCookieOptions().secure, path: "/", maxAge: 60 * 60 * 24 * 30 });
    revalidatePath("/", "layout");
    return { ok: true, status: 200, message: "Contexto da organizacao alterado com seguranca." };
  } catch (error) { return result(error); }
}

export async function createRoom(form: FormData): Promise<MutationResult> {
  try {
    const organizationId = text(form, "organizationId");
    const room = await authenticatedApi<{ id: string; name: string }>("/v1/rooms", { method: "POST", organizationId, headers: { "content-type": "application/json" }, body: JSON.stringify({ name: text(form, "name"), description: text(form, "description") || null, isPrivate: form.get("isPrivate") === "on" }) });
    revalidatePath("/operacao/salas");
    return { ok: true, status: 201, message: `Sala ${room.name} criada.`, data: { roomId: room.id } };
  } catch (error) { return result(error); }
}

export async function createMessage(form: FormData): Promise<MutationResult> {
  try {
    const roomId = text(form, "roomId");
    if (shouldUseMockWorkspace()) return { ok: true, status: 201, message: "Mensagem entregue e reconciliada.", data: { messageId: `mock-${text(form, "clientId") || "message"}`, roomId } };
    const message = await authenticatedApi<{ id: string }>(`/v1/rooms/${encodeURIComponent(roomId)}/messages`, { method: "POST", organizationId: text(form, "organizationId"), headers: { "content-type": "application/json" }, body: JSON.stringify({ body: text(form, "body"), clientId: text(form, "clientId") || randomUUID() }) });
    revalidatePath("/colaboracao/sala");
    return { ok: true, status: 201, message: "Mensagem entregue e reconciliada.", data: { messageId: message.id, roomId } };
  } catch (error) { return result(error); }
}

export async function createTask(form: FormData): Promise<MutationResult> {
  try {
    const dependencies = form.getAll("dependencies").filter((value): value is string => typeof value === "string" && Boolean(value));
    const payload = {
      goal: text(form, "goal"),
      title: text(form, "title") || null,
      risk: text(form, "risk") || "low",
      assigneeId: text(form, "assigneeId") || null,
      roomId: text(form, "roomId") || null,
      sourceMessageId: text(form, "sourceMessageId") || null,
      dependencies
    };
    if (shouldUseMockWorkspace()) return { ok: true, status: 201, message: `Tarefa ${payload.title || payload.goal} criada.`, data: { taskId: "mock-task", version: 1 } };
    const response = await authenticatedApi<{ task: { id: string; version: number; title: string } }>("/v1/tasks", { method: "POST", organizationId: text(form, "organizationId"), headers: { "content-type": "application/json", "Idempotency-Key": text(form, "idempotencyKey") || randomUUID() }, body: JSON.stringify(payload) });
    revalidatePath("/operacao/tarefas");
    return { ok: true, status: 201, message: `Tarefa ${response.task.title} criada.`, data: { taskId: response.task.id, version: response.task.version } };
  } catch (error) { return result(error); }
}

export async function replaceTaskDependencies(form: FormData): Promise<MutationResult> {
  try {
    const taskId = text(form, "taskId");
    const dependencies = form.getAll("dependencies").filter((value): value is string => typeof value === "string" && Boolean(value));
    const task = await authenticatedApi<{ id: string; version: number }>(`/v1/tasks/${encodeURIComponent(taskId)}/dependencies`, {
      method: "PATCH",
      organizationId: text(form, "organizationId"),
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ dependencies, expectedVersion: Number(text(form, "expectedVersion")) })
    });
    revalidatePath("/operacao/tarefa-detalhe");
    return { ok: true, status: 200, message: "Dependencias atualizadas.", data: { taskId: task.id, version: task.version } };
  } catch (error) { return result(error); }
}

export async function decideApproval(form: FormData): Promise<MutationResult> {
  try {
    let approvalId = text(form, "approvalId");
    let expectedRound = Number(text(form, "expectedRound") || "1");
    const organizationId = text(form, "organizationId");
    if (shouldUseMockWorkspace()) return { ok: true, status: 200, message: `Decisao ${text(form, "decision")} registrada de forma auditavel.` };
    if (!approvalId) {
      const page = await authenticatedApi<{ items: Array<{ id: string; round: number; status: string }> }>("/v1/approvals", { organizationId });
      const pending = page.items.find((item) => item.status === "pending");
      if (!pending) return { ok: false, status: 409, message: "Nao ha aprovacao pendente para decidir." };
      approvalId = pending.id; expectedRound = pending.round;
    }
    await authenticatedApi(`/v1/approvals/${encodeURIComponent(approvalId)}/decision`, { method: "POST", organizationId, headers: { "content-type": "application/json" }, body: JSON.stringify({ decision: text(form, "decision"), comment: text(form, "comment") || null, expectedRound }) });
    revalidatePath("/governanca/aprovacao-detalhe");
    return { ok: true, status: 200, message: "Decisao registrada de forma auditavel." };
  } catch (error) { return result(error); }
}

export async function initiateArtifact(form: FormData): Promise<MutationResult> {
  try {
    const organizationId = text(form, "organizationId");
    const initiated = await authenticatedApi<{ artifactId: string; uploadUrl: string; requiredHeaders: Record<string, string> }>("/v1/artifacts/uploads", { method: "POST", organizationId, headers: { "content-type": "application/json" }, body: JSON.stringify({ filename: text(form, "filename"), mimeType: text(form, "mimeType") || "application/octet-stream", sizeBytes: Number(text(form, "sizeBytes")), checksumSha256: text(form, "checksumSha256") }) });
    return { ok: true, status: 201, message: "Upload assinado iniciado.", data: { artifactId: initiated.artifactId, uploadUrl: initiated.uploadUrl, requiredHeaders: initiated.requiredHeaders } };
  } catch (error) { return result(error); }
}

export async function confirmArtifact(form: FormData): Promise<MutationResult> {
  try {
    const artifactId = text(form, "artifactId");
    const confirmed = await authenticatedApi<{ quarantineStatus: string }>(`/v1/artifacts/${encodeURIComponent(artifactId)}/confirm`, { method: "POST", organizationId: text(form, "organizationId"), headers: { "content-type": "application/json" }, body: JSON.stringify({ checksumSha256: text(form, "checksumSha256") }) });
    revalidatePath("/colaboracao/arquivos");
    return { ok: true, status: 202, message: `Upload confirmado; quarentena ${confirmed.quarantineStatus}.`, data: { artifactId } };
  } catch (error) { return result(error); }
}

export async function createContentAsset(form: FormData): Promise<MutationResult> {
  try {
    const response = await authenticatedApi<{ asset?: { id: string; title: string }; replayed: boolean }>("/v1/content/assets", { method: "POST", organizationId: text(form, "organizationId"), headers: { "content-type": "application/json", "Idempotency-Key": text(form, "idempotencyKey") || randomUUID() }, body: JSON.stringify({ brief: text(form, "brief"), title: text(form, "title") || null, channels: [text(form, "channel") || "email"], variants: [] }) });
    revalidatePath("/comercial/conteudo");
    return { ok: true, status: response.replayed ? 200 : 201, message: response.replayed ? "Conteudo recuperado sem duplicacao." : "Conteudo criado e versionado.", ...(response.asset ? { data: { assetId: response.asset.id } } : {}) };
  } catch (error) { return result(error); }
}

export async function scheduleExperiment(form: FormData): Promise<MutationResult> {
  try {
    const organizationId = text(form, "organizationId");
    const id = text(form, "experimentId");
    const updatedAt = text(form, "expectedUpdatedAt");
    if (shouldUseMockWorkspace()) return { ok: true, status: 200, message: "Experimento configurado e iniciado; hipotese e variantes agora estao bloqueadas.", data: { experimentId: id, status: "running", immutableFields: ["hypothesis", "variants"] } };
    if (!id || !updatedAt) return { ok: false, status: 409, message: "Nenhum experimento draft esta disponivel para configuracao." };
    const start = new Date(); const end = new Date(start.getTime() + 14 * 86400000);
    const configured = await authenticatedApi<{ experiment?: { updatedAt?: string; updated_at?: string } }>(`/v1/experiments/${encodeURIComponent(id)}`, { method: "PATCH", organizationId, headers: { "content-type": "application/json" }, body: JSON.stringify({ hypothesis: text(form, "hypothesis"), window: { start: start.toISOString(), end: end.toISOString() }, expectedUpdatedAt: updatedAt }) });
    const configuredAt = configured.experiment?.updatedAt ?? configured.experiment?.updated_at;
    if (!configuredAt) return { ok: false, status: 502, message: "A API nao retornou a versao configurada do experimento." };
    const started = await authenticatedApi<{ experiment?: { status?: string }; immutableFields?: string[]; replayed?: boolean }>(`/v1/experiments/${encodeURIComponent(id)}/start`, { method: "POST", organizationId, headers: { "content-type": "application/json" }, body: JSON.stringify({ expectedUpdatedAt: configuredAt }) });
    if (started.experiment?.status !== "running") return { ok: false, status: 502, message: "A API nao confirmou o inicio do experimento." };
    revalidatePath("/aprendizado/experimento-detalhe");
    return { ok: true, status: 200, message: started.replayed ? "Experimento ja estava em execucao; estado reconciliado." : "Experimento configurado e iniciado; hipotese e variantes agora estao bloqueadas.", data: { experimentId: id, status: "running", immutableFields: started.immutableFields ?? [] } };
  } catch (error) { return result(error); }
}

export async function decidePortal(form: FormData): Promise<MutationResult> {
  try {
    if (shouldUseMockWorkspace()) return { ok: true, status: 200, message: `Resposta ${text(form, "decision")} registrada e auditada.` };
    await publicApi(`/v1/portal/items/${encodeURIComponent(text(form, "token"))}/decision`, { method: "POST", headers: { "content-type": "application/json", "Idempotency-Key": text(form, "idempotencyKey") || randomUUID() }, body: JSON.stringify({ decision: text(form, "decision"), comment: text(form, "comment") || null, expectedRound: Number(text(form, "expectedRound") || "1") }) });
    return { ok: true, status: 200, message: "Resposta externa registrada e auditada." };
  } catch (error) { return result(error); }
}
