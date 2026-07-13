export type MutationFailure = { ok: false; status: number; message: string };
export type MutationResult = { ok: boolean; message: string; status: number; data?: Record<string, unknown> };

export function mutationFailure(status: number, detail?: string): MutationFailure {
  const messages: Record<number, string> = {
    401: "Sua sessao expirou. Entre novamente.",
    403: "Voce nao tem permissao para esta operacao.",
    409: "O registro mudou ou esta operacao ja foi aplicada. Recarregue e tente novamente."
  };
  return {
    ok: false,
    status,
    message: messages[status] ?? (status >= 500 ? "Servico indisponivel. Tente novamente sem repetir a operacao." : detail || "Operacao invalida.")
  };
}
