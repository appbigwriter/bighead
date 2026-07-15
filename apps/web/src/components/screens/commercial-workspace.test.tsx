import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

let query = new URLSearchParams();
vi.mock("next/navigation", () => ({ useSearchParams: () => query }));

import { CommercialWorkspace } from "./commercial-workspace";

const leadId = "7724feab-c777-4b59-9d70-7598d40662ba";
const lead = { id: leadId, accountId: null, contactId: null, ownerUserId: "11111111-1111-4111-8111-111111111111", status: "qualified", source: "evento", icpScore: .87, scoreFactors: {}, scoreAlgorithmVersion: "v1", nextAction: "Ligar", nextActionAt: "2030-01-01T12:00:00Z", createdAt: "2029-01-01T12:00:00Z" };
function response(body: unknown, status = 200) { return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })); }
function requestUrl(input: RequestInfo | URL) { return typeof input === "string" ? input : input instanceof URL ? input.href : input.url; }

describe("CommercialWorkspace", () => {
  beforeEach(() => { query = new URLSearchParams(); vi.restoreAllMocks(); });

  it("renders real lead fields and links to the returned id", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => response({ items: [lead], counters: { total: 1 }, nextCursor: null }));
    render(<CommercialWorkspace mode="leads" />);
    expect(await screen.findByText("87%")).toBeTruthy();
    expect(screen.getByText("evento")).toBeTruthy();
    expect(screen.getByRole("link", { name: /evento/ }).getAttribute("href")).toContain(leadId);
  });

  it("preserves follow-up fields and idempotency key across retry, then appends timeline", async () => {
    query = new URLSearchParams(`leadId=${leadId}`);
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockImplementationOnce(() => response({ lead, timeline: [], signals: [], suggestions: [] }))
      .mockImplementationOnce(() => response({ detail: "Provider indisponivel" }, 503))
      .mockImplementationOnce(() => response({ lead: { ...lead, nextAction: "Enviar proposta" }, timelineItem: { type: "follow_up", action: "Enviar proposta", dueAt: "2030-02-01T12:00:00Z" }, replayed: false }, 201));
    render(<CommercialWorkspace mode="detail" />);
    await screen.findByRole("heading", { name: /Lead 7724feab/ });
    fireEvent.change(screen.getByLabelText("Acao"), { target: { value: "Enviar proposta" } });
    fireEvent.change(screen.getByLabelText("Prazo"), { target: { value: "2030-02-01T12:00" } });
    fireEvent.submit(screen.getByRole("button", { name: "Criar follow-up" }).closest("form")!);
    expect(await screen.findByRole("button", { name: "Tentar novamente" })).toBeTruthy();
    expect(screen.getByLabelText<HTMLInputElement>("Acao").value).toBe("Enviar proposta");
    const firstKey = new Headers(fetchMock.mock.calls.at(1)?.[1]?.headers).get("Idempotency-Key");
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    await screen.findByText("Follow-up salvo.");
    const retryKey = new Headers(fetchMock.mock.calls.at(2)?.[1]?.headers).get("Idempotency-Key");
    expect(retryKey).toBe(firstKey);
    expect(screen.getAllByText("Enviar proposta")).toHaveLength(2);
  });

  it("shows stage-specific fields and reloads the board after persistence", async () => {
    const board = { stages: [{ id: "discovery", label: "Descoberta", count: 1, amount: 1000, opportunities: [{ id: leadId, name: "Atlas", stage: "discovery", amount: 1000, currency: "BRL", probability: 30, expectedCloseDate: null, leadId, accountId: null, updatedAt: "2030-01-01T00:00:00Z" }] }], totals: { opportunities: 1, amount: 1000 } };
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(() => response(board));
    render(<CommercialWorkspace mode="pipeline" />);
    fireEvent.click(await screen.findByRole("button", { name: /Atlas/ }));
    fireEvent.change(screen.getByLabelText("Nova etapa"), { target: { value: "negotiation" } });
    expect(screen.getByLabelText("Valor")).toHaveAttribute("step", "0.01");
    expect(screen.getByLabelText("Probabilidade")).toBeTruthy();
    fireEvent.submit(screen.getByRole("button", { name: "Confirmar etapa" }).closest("form")!);
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => requestUrl(url).includes(`/opportunities/${leadId}/stage`))).toBe(true));
    await waitFor(() => expect(fetchMock.mock.calls.filter(([url]) => url === "/api/commercial/pipeline")).toHaveLength(2));
  });
});
