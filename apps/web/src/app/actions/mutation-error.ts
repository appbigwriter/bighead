import { mutationFailure } from "@/lib/mutation-result";

import type { MutationResult } from "@/lib/mutation-result";

export function mutationResultFromError(error: unknown): MutationResult {
  const httpError = error instanceof Error && "status" in error && typeof error.status === "number" ? error as Error & { status: number } : null;
  if (httpError && /dependency cycle/i.test(httpError.message)) {
    return {
      ok: false,
      status: httpError.status,
      message: "Corrija as dependencias destacadas antes de salvar.",
      data: { fieldErrors: { dependencies: "Dependencia circular detectada." } }
    };
  }
  const status = httpError?.status ?? 500;
  return mutationFailure(status, error instanceof Error ? error.message : undefined);
}
