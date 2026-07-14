import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { search } = vi.hoisted(() => ({ search: { value: "" } }));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(search.value) }));

import { ApprovalsWorkspace } from "./approvals-workspace";

const approvalId = "30000000-0000-4000-8000-000000000001";
const list = { items: [
  { id: approvalId, taskId: "40000000-0000-4000-8000-000000000001", title: "Publicar campanha", status: "pending", riskLevel: "high", round: 2, dueAt: "2099-07-15T12:00:00Z" },
  { id: "30000000-0000-4000-8000-000000000002", title: "Liberar dados", status: "pending", riskLevel: "critical", round: 1, dueAt: "2020-01-01T12:00:00Z" },
  { id: "30000000-0000-4000-8000-000000000003", title: "Revisar contrato", status: "approved", riskLevel: "medium", round: 1, dueAt: "2026-07-11T12:00:00Z" }
] };
const baseDetail = {
  approval: { id: approvalId, status: "pending", risk_level: "high", round: 2, due_at: "2099-07-15T12:00:00Z" },
  task: { id: "40000000-0000-4000-8000-000000000001", title: "Publicar campanha", objective: "Validar conformidade antes da publicação" },
  requester: { id: "10000000-0000-4000-8000-000000000001" },
  evidence: [{ type: "artifact", artifact: { id: "a-1", name: "campanha-final.pdf", kind: "document" } }, { type: "qa_evaluation", evaluation: { id: "e-1", score: 96, passed: true } }],
  impact: { taskStatus: "waiting_human", activeRunCount: 1, estimatedCost: "42.50", slaAt: "2099-07-15T13:00:00Z" },
  availableActions: ["approved", "changes_requested", "rejected"], decisionBlockedReason: null
};
const history = { items: [{ id: "d-1", decision: "changes_requested", actor: { type: "user", id: "20000000-0000-4000-8000-000000000001" }, comment: "Corrigir dados", decidedAt: "2026-07-13T12:00:00Z" }] };
let detail: Omit<typeof baseDetail, "decisionBlockedReason"> & { decisionBlockedReason: string | null } = baseDetail;
let decisionStatus = 200;

function url(input: RequestInfo | URL) { return typeof input === "string" ? input : input instanceof URL ? input.href : input.url; }
function routeFetch(input: RequestInfo | URL, init?: RequestInit) {
  const target = url(input);
  if (target === "/api/approvals") return Promise.resolve(Response.json(list));
  if (target.endsWith("/decisions")) return Promise.resolve(Response.json(history));
  if (target.endsWith("/decision") && init?.method === "POST") {
    if (decisionStatus !== 200) return Promise.resolve(Response.json({ detail: "upstream" }, { status: decisionStatus }));
    detail = { ...baseDetail, approval: { ...baseDetail.approval, status: "approved" }, availableActions: [], decisionBlockedReason: "approval_already_decided" };
    return Promise.resolve(Response.json({ approval: detail.approval, roundResult: "approved", nextActions: ["resume_task"] }));
  }
  if (target.includes(`/api/approvals/${approvalId}`)) return Promise.resolve(Response.json(detail));
  return Promise.reject(new Error(`Unexpected request: ${target}`));
}

describe("ApprovalsWorkspace", () => {
  beforeEach(() => { search.value = ""; detail = baseDetail; decisionStatus = 200; vi.stubGlobal("fetch", vi.fn(routeFetch)); });
  afterEach(() => vi.unstubAllGlobals());

  it("separates pending, overdue and decided approvals using real response fields", async () => {
    render(<ApprovalsWorkspace mode="inbox" />);
    expect(await screen.findByText("Publicar campanha")).toBeTruthy();
    expect(screen.queryByText("Liberar dados")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Vencidas 1/ }));
    expect(screen.getByText("Liberar dados")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: /Decididas 1/ }));
    expect(screen.getByText("Revisar contrato")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Revisar contrato/ })).toHaveAttribute("href", "/governanca/aprovacao-detalhe?approvalId=30000000-0000-4000-8000-000000000003");
    expect(document.body.textContent).not.toMatch(/T20|endpoint|OpenAPI|fixture|estados previstos/i);
  });

  it("shows requester, risk, evidence, impact and actor/timestamp history", async () => {
    search.value = `approvalId=${approvalId}`;
    render(<ApprovalsWorkspace mode="detail" />);
    expect(await screen.findByRole("heading", { name: "Publicar campanha" })).toBeTruthy();
    expect(screen.getByText("campanha-final.pdf")).toBeTruthy();
    expect(screen.getByText(/Nota 96/)).toBeTruthy();
    expect(screen.getByText("10000000…0001")).toBeTruthy();
    expect(screen.getByText("Pessoa 20000000…0001")).toBeTruthy();
    expect(screen.getByText("Corrigir dados")).toBeTruthy();
    expect(screen.getByText("1")).toBeTruthy();
  });

  it("blocks self-approval in the UI", async () => {
    detail = { ...baseDetail, availableActions: [], decisionBlockedReason: "self_approval_prohibited" };
    search.value = `approvalId=${approvalId}`;
    render(<ApprovalsWorkspace mode="detail" />);
    expect(await screen.findByText("Você solicitou esta aprovação. Outra pessoa deve decidir.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Confirmar decisão" })).toBeDisabled();
  });

  it("submits expectedRound, persists the decision and offers reload on 409", async () => {
    search.value = `approvalId=${approvalId}`;
    const view = render(<ApprovalsWorkspace mode="detail" />);
    await screen.findByText("campanha-final.pdf");
    fireEvent.change(screen.getByLabelText("Comentário"), { target: { value: "Risco revisado" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar decisão" }));
    await screen.findByText("Decisão registrada. O trabalho relacionado foi atualizado.");
    const post = vi.mocked(fetch).mock.calls.find(([input, init]) => url(input).endsWith("/decision") && init?.method === "POST");
    const requestBody = post?.[1]?.body;
    expect(typeof requestBody).toBe("string");
    expect(JSON.parse(requestBody as string)).toEqual({ decision: "approved", comment: "Risco revisado", expectedRound: 2 });
    expect(screen.getByText("Aprovada")).toBeTruthy();

    detail = baseDetail; decisionStatus = 409;
    view.unmount();
    render(<ApprovalsWorkspace mode="detail" />);
    await screen.findByText("campanha-final.pdf");
    fireEvent.change(screen.getByLabelText("Comentário"), { target: { value: "Não perder" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirmar decisão" }));
    expect(await screen.findByText("Outra pessoa decidiu esta rodada. Recarregue antes de continuar.")).toBeTruthy();
    expect(screen.getByLabelText("Comentário")).toHaveValue("Não perder");
    expect(screen.getByRole("button", { name: "Recarregar rodada" })).toBeTruthy();
  });
});
