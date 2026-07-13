export const transverseStates = [
  { name: "Loading", description: "Skeletons e blocos progressivos.", tone: "neutral" },
  { name: "Vazio", description: "Explica proxima acao e contexto.", tone: "neutral" },
  { name: "Erro", description: "Mostra trace ID e retry seguro.", tone: "risk" },
  { name: "Sem permissao", description: "Nao vaza existencia do recurso.", tone: "neutral" },
  { name: "Offline", description: "Preserva rascunho e oferece retry idempotente ao reconectar.", tone: "neutral" },
  { name: "Sucesso", description: "Confirma o resultado e indica a proxima acao disponivel.", tone: "neutral" }
] as const;
