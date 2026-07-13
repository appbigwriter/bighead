import { describe, expect, it } from "vitest";

import {
  canApprove,
  filterKnowledgeResults,
  missingStageFields,
  retryPublication,
  validateWorkflow,
  type FailedPublication,
  type KnowledgeResult
} from "./sprint2-domain-rules";

describe("Sprint 2 domain rules", () => {
  it("enforces segregation of duties when the policy requires it", () => {
    expect(canApprove("camila", "camila", true)).toBe(false);
    expect(canApprove("camila", "rafael", true)).toBe(true);
    expect(canApprove("camila", "camila", false)).toBe(true);
  });

  it("rejects cycles, missing nodes and incompatible schemas", () => {
    const nodes = [
      { id: "briefing", input: "brief", output: "lead" },
      { id: "score", input: "lead", output: "decision" },
      { id: "approve", input: "decision", output: "publication" }
    ];
    const edges = [{ source: "briefing", target: "score" }, { source: "score", target: "approve" }];
    expect(validateWorkflow(nodes, edges)).toEqual([]);
    expect(validateWorkflow(nodes, [...edges, { source: "approve", target: "briefing" }])).toContain("Ciclo indevido detectado.");
    expect(validateWorkflow(nodes, [...edges, { source: "missing", target: "approve" }])).toContain("Aresta referencia node inexistente.");
    expect(validateWorkflow(nodes.map((node) => node.id === "approve" ? { ...node, input: "asset" } : node), edges).join(" ")).toContain("Schema incompativel");
    expect(validateWorkflow([...nodes, { id: "orphan", input: "x", output: "y" }], edges)).toContain("Grafo possui componente desconectado.");
    expect(validateWorkflow([...nodes, nodes[0]!], edges)).toContain("Node duplicado detectado.");
    expect(validateWorkflow([...nodes, { id: "", input: "", output: "" }], edges)).toContain("Node possui id ou schema vazio.");
  });

  it("excludes contested and cross-tenant knowledge before applying facets", () => {
    const items: KnowledgeResult[] = [
      { id: "active", tenantId: "atlas", title: "Politica Atlas", source: "handbook", score: 0.91, status: "active" },
      { id: "contested", tenantId: "atlas", title: "Politica contestada", source: "handbook", score: 0.99, status: "contested" },
      { id: "foreign", tenantId: "beacon", title: "Politica Beacon", source: "handbook", score: 0.98, status: "active" },
      { id: "low", tenantId: "atlas", title: "Resumo Atlas", source: "crm", score: 0.7, status: "active" }
    ];
    expect(filterKnowledgeResults(items, { tenantId: "atlas", query: "", source: "all", minScore: 0.8 }).map((item) => item.id)).toEqual(["active"]);
    expect(filterKnowledgeResults(items, { tenantId: "atlas", query: "politica", source: "crm", minScore: 0 }).map((item) => item.id)).toEqual([]);
  });

  it("lists required fields for a stage transition", () => {
    expect(missingStageFields("proposal", { amount: "", closeDate: "" })).toEqual(["amount", "closeDate"]);
    expect(missingStageFields("proposal", { amount: "150000", closeDate: "2026-08-01" })).toEqual([]);
    expect(missingStageFields("lost", { lossReason: "" })).toEqual(["lossReason"]);
  });

  it("retries a failed publication once without changing its payload or idempotency key", () => {
    const failed: FailedPublication = { payload: "{\"assetId\":\"44\"}", idempotencyKey: "atlas-44", attempts: 1, status: "provider_error" };
    const queued = retryPublication(failed);
    expect(queued).toEqual({ ...failed, attempts: 2, status: "queued" });
    expect(retryPublication(queued)).toBe(queued);
  });
});
