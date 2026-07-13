import { mutationFailure, type MutationResult } from "./mutation-result";

function text(form: FormData, name: string) {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function isMutationResult(value: unknown): value is MutationResult {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const candidate = value as Partial<MutationResult>;
  return typeof candidate.ok === "boolean" && typeof candidate.status === "number" && typeof candidate.message === "string";
}

export async function transitionTask(form: FormData): Promise<MutationResult> {
  const taskId = text(form, "taskId");
  if (!taskId) return mutationFailure(422, "Tarefa obrigatoria.");
  try {
    const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}/transition`, {
      method: "POST",
      cache: "no-store",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        targetState: text(form, "targetState"),
        expectedVersion: Number(text(form, "expectedVersion")),
        reason: text(form, "reason") || null
      })
    });
    const result: unknown = await response.json().catch(() => null);
    if (isMutationResult(result)) return result;
    return mutationFailure(response.status, "Resposta invalida da API.");
  } catch {
    return mutationFailure(503);
  }
}
