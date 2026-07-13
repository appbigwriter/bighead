import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { getWorkspaceSnapshot } from "@/lib/mock-workspace";

import { HomeDashboard } from "./home-dashboard";

describe("HomeDashboard", () => {
  it("turns real snapshot tasks and approvals into an actionable operating view", () => {
    const snapshot = {
      ...getWorkspaceSnapshot(),
      currentOrganization: "Atlas Operações",
      taskOptions: [
        { id: "task-active", name: "Revisar plano de lançamento", status: "in_progress", version: 3, riskLevel: "high", dueAt: "2026-07-14T12:00:00Z", assigneeId: "user-42", nextAction: "Validar artefato" },
        { id: "task-critical", name: "Conter falha crítica", status: "blocked", version: 1, riskLevel: "critical", dueAt: "2026-07-15T12:00:00Z" },
        { id: "task-done", name: "Briefing aprovado", status: "done", version: 4 }
      ],
      approvalOptions: [
        { id: "approval-pending", name: "Campanha enterprise", status: "pending", round: 2 },
        { id: "approval-done", name: "Política de preços", status: "approved", round: 1 }
      ],
      analyticsDrilldowns: [
        { card: "total" as const, dimension: "overdue", value: 2, recordIds: [], recordCount: 2, recordsTruncated: false, recordsEndpoint: "/v1/analytics/summary/records" as const, periodFrom: "", periodTo: "" }
      ],
      adminMoments: [
        { id: "event-1", title: "Workflow concluído", description: "A entrega foi registrada no histórico do workspace.", meta: "done" }
      ]
    };

    const view = render(<HomeDashboard snapshot={snapshot} />);

    expect(screen.getByRole("heading", { name: "Operação de Atlas Operações" })).toBeTruthy();
    expect(screen.getByText("Revisar plano de lançamento")).toBeTruthy();
    expect(screen.getByText("Campanha enterprise")).toBeTruthy();
    expect(screen.getByText("Workflow concluído")).toBeTruthy();
    expect(screen.getByText("ID do responsável: user-42")).toBeTruthy();
    expect(screen.getByText("Risco Alto")).toBeTruthy();
    expect(screen.getByText("Próxima ação: Validar artefato")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Tarefas ativas nesta página 2/ })).toBeTruthy();
    expect(within(screen.getByRole("list", { name: "Prioridades abertas" })).getAllByRole("listitem")[0]?.textContent).toContain("Conter falha crítica");
    expect(screen.getByRole("link", { name: /Nova tarefa/ }).getAttribute("href")).toBe("/tarefas/criar");
    expect(screen.getByRole("link", { name: /Revisar plano de lançamento/ }).getAttribute("href")).toContain("taskId=task-active");
    expect(screen.getByText("Custo no período").closest("a")).toBeNull();
    expect(screen.getByText("SLA em risco").closest("a")).toBeNull();
    expect(view.container.querySelector("main")).toBeNull();
    expect(view.container.textContent).not.toMatch(/T06|\/v1\/|fixture|crit[eé]rio|endpoint/i);
  });

  it("ranks a critical approval globally before more than six low-risk tasks", () => {
    const snapshot = {
      ...getWorkspaceSnapshot(),
      taskOptions: Array.from({ length: 7 }, (_, index) => ({
        id: `task-low-${index}`,
        name: `Tarefa baixa ${index}`,
        status: "in_progress",
        riskLevel: "low",
        dueAt: `2026-07-${String(index + 14).padStart(2, "0")}T12:00:00Z`
      })),
      approvalOptions: [{
        id: "approval-critical",
        name: "Aprovação crítica",
        status: "pending",
        riskLevel: "critical",
        dueAt: "2026-07-20T12:00:00Z",
        assigneeId: "owner-9"
      }],
      adminMoments: []
    };

    render(<HomeDashboard snapshot={snapshot} />);

    const items = within(screen.getByRole("list", { name: "Prioridades abertas" })).getAllByRole("listitem");
    expect(items).toHaveLength(6);
    expect(items[0]?.textContent).toContain("Aprovação crítica");
    expect(items[0]?.textContent).toContain("Risco Crítico");
  });

  it("shows honest unavailable and empty states when the snapshot lacks operational fields", () => {
    const snapshot = {
      ...getWorkspaceSnapshot(),
      taskOptions: [],
      approvalOptions: [],
      analyticsDrilldowns: [],
      adminMoments: []
    };

    render(<HomeDashboard snapshot={snapshot} />);

    expect(screen.getByText("Nenhuma prioridade aberta")).toBeTruthy();
    expect(screen.getByText("Sem leitura de SLA")).toBeTruthy();
    expect(screen.getByText("Custo indisponível")).toBeTruthy();
    expect(screen.getByText("Atividade indisponível")).toBeTruthy();
  });
});
