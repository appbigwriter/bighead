import { readFile } from "node:fs/promises";

const files = {
  collaboration: "docs/frontend-backend/colaboracao.md",
  tasks: "docs/frontend-backend/tarefas-execucoes.md",
  governance: "docs/frontend-backend/governanca-automacao.md",
  commercial: "docs/frontend-backend/conhecimento-comercial.md",
  analytics: "docs/frontend-backend/analytics-administracao.md",
  matrix: "docs/frontend-backend/ENDPOINT-MATRIX.md",
  openapi: "docs/frontend-backend/openapi-snapshot.yaml",
};

const documents = Object.fromEntries(
  await Promise.all(
    Object.entries(files).map(async ([key, path]) => [key, await readFile(path, "utf8")]),
  ),
);

const requirements = {
  collaboration: [
    "createdAt DESC, id DESC",
    "cursor malformado retorna `422`",
    "`clientId`",
    "52_428_800",
    "checksumSha256",
    "quarantineStatus",
  ],
  tasks: [
    "`done` e `canceled` sao terminais",
    "`new`, `triaged`, `in_progress`",
    "`lockedBy`, `lockedUntil` e `heartbeatAt`",
    "`previousRunId`",
    "`validation`, `provider`, `tool`, `timeout`, `permission`, `quota`, `lease_expired`",
  ],
  governance: [
    "## Handoff de comandos",
    "Decidir aprovacao",
    "Decidir no portal",
    "Validar skill",
    "Validar workflow",
    "Rollback workflow",
    "Instanciar playbook",
    "`queued -> running -> succeeded/failed`",
  ],
  commercial: [
    "## Schema de importacao CRM",
    '"consentBasis"',
    '"rows"',
    "1..1000",
    "## Lifecycle de jobs",
    "queued -> running -> succeeded|partially_succeeded|failed|canceled",
    "`rowIndex`",
  ],
  analytics: [
    "Cobertura de `T46-T56`",
    "`attributionModel`",
    "`reconciliation`",
    "`X-BigHead-Event-Id`",
    "at-least-once",
    "auditoria append-only",
  ],
};

for (const [document, expectedFragments] of Object.entries(requirements)) {
  for (const fragment of expectedFragments) {
    if (!documents[document].includes(fragment)) {
      throw new Error(`${files[document]} does not prove required handoff fragment: ${fragment}`);
    }
  }
}

for (let screen = 10; screen <= 56; screen += 1) {
  const identifier = `T${String(screen).padStart(2, "0")}`;
  if (!documents.matrix.includes(`| ${identifier} |`)) {
    throw new Error(`Endpoint matrix is missing ${identifier}`);
  }
}

const requiredOperations = [
  "/v1/rooms/{roomId}/messages:",
  "/v1/artifacts/uploads:",
  "/v1/tasks/{taskId}/transition:",
  "/v1/runs/{runId}/retry:",
  "/v1/approvals/{approvalId}/decision:",
  "/v1/skills/{skillId}/validate:",
  "/v1/workflows/{workflowId}/validate:",
  "/v1/playbooks/{playbookId}/instantiate:",
  "/v1/knowledge/documents:",
  "/v1/crm/imports:",
  "/v1/content/publications/{id}/retry:",
  "/v1/analytics/operations:",
  "/v1/analytics/agents:",
  "/v1/analytics/costs:",
  "/v1/analytics/funnel:",
  "/v1/organizations/{organizationId}:",
  "/v1/integrations:",
  "/v1/audit/events:",
];

for (const operation of requiredOperations) {
  if (!documents.openapi.includes(operation)) {
    throw new Error(`OpenAPI snapshot is missing documented operation ${operation}`);
  }
}

console.log("Sprint 2 handoff verified: T10-T56 matrix, schemas, lifecycle and OpenAPI operations.");
