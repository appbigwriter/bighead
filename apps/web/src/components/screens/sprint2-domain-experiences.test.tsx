import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Sprint2DomainExperience } from "./sprint2-domain-experiences";

const analyticsDrilldowns = [
  { card: "total" as const, dimension: "in_progress", value: 101, recordIds: ["11111111-1111-4111-8111-111111111111"], recordCount: 101, recordsTruncated: true, recordsEndpoint: "/v1/analytics/summary/records" as const, periodFrom: "2026-06-01T00:00:00Z", periodTo: "2026-07-01T00:00:00Z" },
  { card: "total" as const, dimension: "overdue", value: 1, recordIds: ["22222222-2222-4222-8222-222222222222"], recordCount: 1, recordsTruncated: false, recordsEndpoint: "/v1/analytics/summary/records" as const, periodFrom: "2026-06-01T00:00:00Z", periodTo: "2026-07-01T00:00:00Z" }
];
const experience = (code: Parameters<typeof Sprint2DomainExperience>[0]["code"]) =>
  <Sprint2DomainExperience analyticsDrilldowns={analyticsDrilldowns} code={code} tenantId="fixture-acme" />;

describe("Sprint2DomainExperience", () => {
  it("blocks self-approval and records a segregated decision", () => {
    render(experience("T20"));
    const approve = screen.getByRole("button", { name: "Aprovar entrega" });
    expect(approve).toBeDisabled();
    expect(screen.getByText(/identidade da sessao/)).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Autoaprovacao bloqueada");
    expect(approve).toBeDisabled();
  });

  it("requires impact review for model and skill consumers", () => {
    render(experience("T29"));
    const disable = screen.getByRole("button", { name: "Desabilitar recurso" });
    expect(screen.getByText("Agente SDR v12")).toBeInTheDocument();
    expect(disable).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Recurso de automacao"), { target: { value: "skill:enrichment" } });
    expect(screen.getByText("Agente Research v4")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(disable);
    expect(screen.getByRole("status")).toHaveTextContent("Recurso desabilitado");
  });

  it("shows skill consumers on the dedicated skills screen", () => {
    render(experience("T27"));
    expect(screen.getByText("Agente Research v4")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Desabilitar recurso" })).toBeDisabled();
  });

  it.each(["T30", "T33"] as const)("publishes an immutable version and renders its diff for %s", (code) => {
    render(experience(code));
    const oldVersion = screen.getByTestId("published-v3").textContent;
    fireEvent.change(screen.getByLabelText("Novo draft da publicacao"), { target: { value: "Use apenas fontes aprovadas e cite o score." } });
    fireEvent.click(screen.getByRole("button", { name: "Publicar nova versao" }));
    expect(screen.getByTestId("published-v3").textContent).toBe(oldVersion);
    expect(screen.getByTestId("publication-diff")).toHaveTextContent("- Use fontes aprovadas.");
    expect(screen.getByTestId("publication-diff")).toHaveTextContent("+ Use apenas fontes aprovadas e cite o score.");
    expect(screen.getByLabelText("Novo draft da publicacao")).toBeDisabled();
  });

  it("blocks invalid workflow graphs and publishes only the restored graph", () => {
    render(experience("T32"));
    const publish = screen.getByRole("button", { name: "Validar e publicar" });
    expect(publish).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Adicionar ciclo" }));
    expect(screen.getByRole("status")).toHaveTextContent("Ciclo indevido detectado");
    expect(publish).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Restaurar grafo" }));
    fireEvent.click(screen.getByRole("button", { name: "Quebrar schema" }));
    expect(screen.getByRole("status")).toHaveTextContent("Schema incompativel");
    expect(publish).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Restaurar grafo" }));
    fireEvent.click(publish);
    expect(screen.getByRole("status")).toHaveTextContent("Versao publicada");
  });

  it("searches only active tenant knowledge with source and score evidence", () => {
    render(experience("T38"));
    const results = screen.getByRole("list", { name: "Resultados semanticos" });
    expect(within(results).getByText("Politica vigente de onboarding")).toBeInTheDocument();
    expect(within(results).getByText("Resumo comercial do tenant atual")).toBeInTheDocument();
    expect(screen.queryByText("Politica antiga contestada")).not.toBeInTheDocument();
    expect(screen.queryByText("Plano secreto de outro tenant")).not.toBeInTheDocument();
    expect(within(results).getByText("Score 0.94")).toBeInTheDocument();
    expect(within(results).getByRole("link", { name: "Fonte: handbook" })).toBeInTheDocument();
    expect(within(results).getAllByText("Tenant: fixture-acme").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByLabelText("Consulta governada"), { target: { value: "contestada" } });
    expect(screen.getByRole("status")).toHaveTextContent("0 resultados autorizados");
  });

  it("requires stage fields before moving an opportunity", () => {
    render(experience("T42"));
    const move = screen.getByRole("button", { name: "Mover oportunidade" });
    expect(move).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent("amount, closeDate");
    fireEvent.change(screen.getByLabelText("Valor da oportunidade"), { target: { value: "150000" } });
    fireEvent.change(screen.getByLabelText("Data de fechamento"), { target: { value: "2026-08-01" } });
    expect(move).toBeEnabled();
    fireEvent.click(move);
    expect(screen.getByRole("status")).toHaveTextContent("Movida para proposal");
  });

  it("changes required fields with the configured destination stage", () => {
    render(experience("T42"));
    fireEvent.change(screen.getByLabelText("Estagio de destino"), { target: { value: "lost" } });
    expect(screen.getByRole("status")).toHaveTextContent("lossReason");
    fireEvent.change(screen.getByLabelText("Motivo da perda"), { target: { value: "Sem budget" } });
    expect(screen.getByRole("button", { name: "Mover oportunidade" })).toBeEnabled();
  });

  it.each([
    { stage: "negotiation", missing: "decisionMaker", label: "Decisor", value: "CFO" },
    { stage: "won", missing: "contractId", label: "Contrato", value: "contract-88" }
  ])("requires the extra configured field for $stage", ({ stage, missing, label, value }) => {
    render(experience("T42"));
    fireEvent.change(screen.getByLabelText("Estagio de destino"), { target: { value: stage } });
    fireEvent.change(screen.getByLabelText("Valor da oportunidade"), { target: { value: "150000" } });
    fireEvent.change(screen.getByLabelText("Data de fechamento"), { target: { value: "2026-08-01" } });
    expect(screen.getByRole("status")).toHaveTextContent(missing);
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
    expect(screen.getByRole("button", { name: "Mover oportunidade" })).toBeEnabled();
  });

  it("preserves a failed publication payload across an idempotent retry", () => {
    render(experience("T45"));
    const payload = screen.getByLabelText<HTMLTextAreaElement>("Payload preservado");
    const original = payload.value;
    const retry = screen.getByRole("button", { name: "Repetir publicacao" });
    fireEvent.click(retry);
    expect(payload.value).toBe(original);
    expect(screen.getByText(/publication-atlas-44/)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Retry enfileirado");
    expect(screen.getByRole("status")).toHaveTextContent("Tentativa 2");
    expect(retry).toBeDisabled();
  });

  it("drills an executive indicator down and continues through the authenticated BFF", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ items: [{ id: "99999999-9999-4999-8999-999999999999" }], total: 101, nextCursor: null }), { status: 200 }));
    vi.stubGlobal("fetch", fetcher);
    render(experience("T48"));
    fireEvent.click(screen.getByRole("button", { name: "Status in_progress (101)" }));
    const records = screen.getByRole("list", { name: "Registros componentes" });
    expect(within(records).getByText("11111111-1111-4111-8111-111111111111")).toBeInTheDocument();
    fireEvent.click(within(records).getByRole("button", { name: /11111111-1111-4111-8111-111111111111/ }));
    expect(screen.getByTestId("component-record")).toHaveTextContent("AnalyticsSummaryDrilldown.recordIds");
    expect(screen.getByTestId("drilldown-coverage")).toHaveTextContent("Exibindo 1 de 101");
    fireEvent.click(screen.getByRole("button", { name: "Carregar proximos registros" }));
    await waitFor(() => expect(fetcher).toHaveBeenCalledWith("/api/analytics/summary/records?dimension=in_progress&from=2026-06-01T00%3A00%3A00Z&to=2026-07-01T00%3A00%3A00Z&limit=100"));
    expect(await screen.findByText("99999999-9999-4999-8999-999999999999")).toBeInTheDocument();
    expect(screen.getByTestId("drilldown-coverage")).toHaveTextContent("Cobertura integral");
    vi.unstubAllGlobals();
    expect(screen.getByRole("status")).toHaveTextContent("tasks.created_at");
  });
});
