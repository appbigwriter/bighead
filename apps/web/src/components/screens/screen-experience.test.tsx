import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { getDefaultScreen, screens } from "@/lib/screen-catalog";
import { getWorkspaceSnapshot } from "@/lib/mock-workspace";
import { ScreenExperience } from "./screen-experience";

const playbookCodes = [
  "T02", "T03", "T09", "T10", "T12", "T13", "T18", "T19", "T20", "T22", "T24",
  "T25", "T26", "T27", "T29", "T30", "T31", "T33", "T34", "T35", "T36", "T37",
  "T39", "T41", "T43", "T44", "T46", "T48", "T49", "T50", "T51", "T52", "T53"
] as const;

describe("ScreenExperience", () => {
  it("renders the default workspace screen with interactive controls", () => {
    render(<ScreenExperience screen={getDefaultScreen()} snapshot={getWorkspaceSnapshot()} />);
    expect(screen.getByRole("heading", { name: /Home operacional/i })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /SLA em risco/i }).length).toBeGreaterThan(0);
  });

  it.each(screens)("covers $code acceptance rules, states and contracts", (definition) => {
    render(<ScreenExperience screen={definition} snapshot={getWorkspaceSnapshot()} />);

    expect(screen.getAllByText(definition.title).length).toBeGreaterThan(0);
    for (const endpoint of definition.endpoints) {
      expect(screen.getAllByText(endpoint).length).toBeGreaterThan(0);
    }
    for (const state of definition.states) {
      expect(screen.getAllByRole("button", { name: state }).length).toBeGreaterThan(0);
    }

    const rule = screen.getByRole("checkbox", { name: definition.checklist[0]! });
    fireEvent.click(rule);
    expect(rule).toHaveProperty("checked", true);
  });

  it.each(playbookCodes)("executes the screen-specific playbook for %s", (code) => {
    const definition = screens.find((item) => item.code === code)!;
    render(<ScreenExperience screen={definition} snapshot={getWorkspaceSnapshot()} />);

    const experience = screen.getByTestId(`screen-playbook-${code}`);
    expect(within(experience).queryByText(/fluxo contratual/i)).toBeNull();

    const playbookState = within(experience).getByTestId(`playbook-state-${code}`);
    expect(playbookState.getAttribute("data-domain")).toBeTruthy();
    fireEvent.click(within(experience).getByRole("button", { name: "Confirmar precondicao" }));
    expect(within(playbookState).getByText("ready")).toBeTruthy();
    fireEvent.click(within(experience).getByTestId(`screen-playbook-action-${code}`));
    expect(within(playbookState).getByText("applied")).toBeTruthy();
    expect(screen.getByText("Ultimo evento").parentElement?.textContent).not.toContain(
      "Nenhuma acao executada"
    );
  });

  it("renders a temporary room message and reconciles it without duplication", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T11")!} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.change(screen.getByLabelText("Nova mensagem da sala"), { target: { value: "Contexto unico" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(screen.getAllByText("Contexto unico")).toHaveLength(1);
    expect(document.querySelector('[data-message-id="temp-1"]')).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Confirmar entrega" }));
    expect(document.querySelector('[data-message-id="temp-1"]')).toBeNull();
    expect(document.querySelector('[data-message-id="msg-101"]')).toBeTruthy();
    expect(screen.getAllByText("Contexto unico")).toHaveLength(1);
  });

  it("retries a failed optimistic message without adding a duplicate", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T11")!} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.change(screen.getByLabelText("Nova mensagem da sala"), { target: { value: "Retry unico" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar" }));
    fireEvent.click(screen.getByRole("button", { name: "Simular falha de envio" }));
    fireEvent.click(screen.getByRole("button", { name: "Tentar novamente" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirmar entrega" }));
    expect(screen.getAllByText("Retry unico")).toHaveLength(1);
  });

  it("appends the next task cursor without replacing the first page", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T14")!} snapshot={getWorkspaceSnapshot()} />);
    const table = document.querySelector(".bh-data-table")!;
    expect(table.querySelectorAll(".bh-data-row")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: /Carregar proxima pagina/ }));
    expect(table.querySelectorAll(".bh-data-row")).toHaveLength(getWorkspaceSnapshot().taskMoments.length);
  });

  it("preserves reviewer text through a 409 conflict and reload", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T16")!} snapshot={getWorkspaceSnapshot()} />);
    const comment = screen.getByLabelText("Comentario da transicao");
    fireEvent.change(comment, { target: { value: "Nao perder este contexto" } });
    fireEvent.click(within(screen.getByTestId("task-transition-control")).getByRole("button", { name: "approved" }));
    expect(screen.getAllByText("Estado critico simulado").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Recarregar versao" }));
    expect(comment).toHaveProperty("value", "Nao perder este contexto");
  });

  it("locks an approval after the immutable decision is recorded", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T21")!} snapshot={getWorkspaceSnapshot()} />);
    const decisionControl = within(screen.getByTestId("approval-decision-control"));
    fireEvent.click(decisionControl.getByRole("button", { name: "approved" }));
    fireEvent.click(screen.getByRole("button", { name: "Registrar decisao" }));
    expect(decisionControl.getByRole("button", { name: "rejected" })).toHaveProperty("disabled", true);
    expect(screen.getByText(/Decisao approved registrada, imutavel e auditavel/)).toBeTruthy();
  });

  it("requires preview before confirming a duplicate merge", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T40")!} snapshot={getWorkspaceSnapshot()} />);
    const confirm = screen.getByRole("button", { name: "Confirmar merge" });
    expect(confirm).toHaveProperty("disabled", true);
    fireEvent.click(screen.getByRole("button", { name: "Gerar preview" }));
    expect(confirm).toHaveProperty("disabled", false);
    fireEvent.click(confirm);
    expect(screen.getByRole("status").textContent).toMatch(/origem preservados/);
  });

  it("distinguishes offline persistence from permission data segregation", () => {
    const definition = screens.find((item) => item.code === "T11")!;
    render(<ScreenExperience screen={definition} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.click(screen.getAllByRole("button", { name: "offline" })[0]!);
    expect(screen.getAllByRole("status").some((node) => node.textContent?.includes("mesma chave idempotente"))).toBe(true);
  });

  it("hides tenant data, counts and actions when permission is denied", () => {
    const definition = screens.find((item) => item.states.includes("permission_denied"))!;
    render(<ScreenExperience screen={definition} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.click(screen.getAllByRole("button", { name: "permission_denied" })[0]!);
    const boundary = screen.getByTestId("permission-boundary");
    expect(within(boundary).getByText("Acesso nao autorizado")).toBeTruthy();
    expect(within(boundary).queryByText(definition.metrics[0]!.value)).toBeNull();
    expect(within(boundary).queryByText(definition.endpoints[0]!)).toBeNull();
    expect(within(boundary).queryByRole("button")).toBeNull();
  });
});
