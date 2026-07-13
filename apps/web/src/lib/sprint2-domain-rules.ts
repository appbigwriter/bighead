export type WorkflowNode = { id: string; input: string; output: string };
export type WorkflowEdge = { source: string; target: string };

export function canApprove(requesterId: string, reviewerId: string, segregationRequired: boolean) {
  return !segregationRequired || requesterId !== reviewerId;
}

export function validateWorkflow(nodes: WorkflowNode[], edges: WorkflowEdge[]) {
  const errors: string[] = [];
  if (nodes.some((node) => !node.id.trim() || !node.input.trim() || !node.output.trim())) errors.push("Node possui id ou schema vazio.");
  if (new Set(nodes.map((node) => node.id)).size !== nodes.length) errors.push("Node duplicado detectado.");
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const adjacency = new Map(nodes.map((node) => [node.id, [] as string[]]));
  for (const edge of edges) {
    const source = byId.get(edge.source);
    const target = byId.get(edge.target);
    if (!source || !target) { errors.push("Aresta referencia node inexistente."); continue; }
    adjacency.get(source.id)?.push(target.id);
    if (source.output !== target.input) errors.push(`Schema incompativel: ${source.id} (${source.output}) -> ${target.id} (${target.input}).`);
  }
  const visiting = new Set<string>();
  const visited = new Set<string>();
  function visit(id: string): boolean {
    if (visiting.has(id)) return true;
    if (visited.has(id)) return false;
    visiting.add(id);
    if ((adjacency.get(id) ?? []).some(visit)) return true;
    visiting.delete(id); visited.add(id); return false;
  }
  if (nodes.some((node) => visit(node.id))) errors.push("Ciclo indevido detectado.");
  if (!nodes.some((node) => !edges.some((edge) => edge.target === node.id))) errors.push("Grafo sem entrada.");
  if (!nodes.some((node) => !edges.some((edge) => edge.source === node.id))) errors.push("Grafo sem saida.");
  if (nodes.length > 0) {
    const connected = new Set<string>();
    const undirected = new Map(nodes.map((node) => [node.id, [] as string[]]));
    for (const edge of edges) {
      if (byId.has(edge.source) && byId.has(edge.target)) {
        undirected.get(edge.source)?.push(edge.target);
        undirected.get(edge.target)?.push(edge.source);
      }
    }
    const visitConnected = (id: string) => {
      if (connected.has(id)) return;
      connected.add(id);
      (undirected.get(id) ?? []).forEach(visitConnected);
    };
    visitConnected(nodes[0]?.id ?? "");
    if (connected.size !== nodes.length) errors.push("Grafo possui componente desconectado.");
  }
  return [...new Set(errors)];
}

export type KnowledgeResult = { id: string; tenantId: string; title: string; source: string; score: number; status: "active" | "contested" };

export function filterKnowledgeResults(items: KnowledgeResult[], options: { tenantId: string; query: string; source: string; minScore: number }) {
  const query = options.query.trim().toLowerCase();
  return items.filter((item) => item.tenantId === options.tenantId
    && item.status === "active"
    && (!query || item.title.toLowerCase().includes(query))
    && (options.source === "all" || item.source === options.source)
    && item.score >= options.minScore);
}

const STAGE_REQUIREMENTS: Record<string, string[]> = {
  proposal: ["amount", "closeDate"],
  negotiation: ["amount", "closeDate", "decisionMaker"],
  won: ["amount", "closeDate", "contractId"],
  lost: ["lossReason"]
};

export function missingStageFields(stage: string, values: Record<string, string>) {
  return (STAGE_REQUIREMENTS[stage] ?? []).filter((field) => !values[field]?.trim());
}

export type FailedPublication = { payload: string; idempotencyKey: string; attempts: number; status: "provider_error" | "queued" };

export function retryPublication(publication: FailedPublication): FailedPublication {
  if (publication.status !== "provider_error") return publication;
  return { ...publication, attempts: publication.attempts + 1, status: "queued" };
}
