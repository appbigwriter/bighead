import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type * as NextNavigation from "next/navigation";

vi.mock("@/app/actions/critical-mutations", () => ({
  createMessage: vi.fn().mockResolvedValue({ ok: true, status: 201, message: "Mensagem entregue e reconciliada." }),
  createRoom: vi.fn().mockResolvedValue({ ok: true, status: 201, message: "Sala criada." }),
  createTask: vi.fn().mockResolvedValue({ ok: true, status: 201, message: "Tarefa criada." }),
  transitionTask: vi.fn().mockResolvedValue({ ok: false, status: 409, message: "O registro mudou." }),
  decideApproval: vi.fn().mockResolvedValue({ ok: true, status: 200, message: "Decisao registrada." }),
  initiateArtifact: vi.fn().mockResolvedValue({ ok: true, status: 201, message: "Upload iniciado.", data: { artifactId: "a", uploadUrl: "https://storage.test", requiredHeaders: {} } }),
  replaceTaskDependencies: vi.fn().mockResolvedValue({ ok: true, status: 200, message: "Dependencias atualizadas." }),
  confirmArtifact: vi.fn().mockResolvedValue({ ok: true, status: 202, message: "Upload confirmado." }),
  createContentAsset: vi.fn().mockResolvedValue({ ok: true, status: 201, message: "Conteudo criado." }),
  scheduleExperiment: vi.fn().mockResolvedValue({ ok: true, status: 200, message: "Janela configurada." }),
  switchTenant: vi.fn().mockResolvedValue({ ok: true, status: 200, message: "Tenant alterado." }),
  decidePortal: vi.fn().mockResolvedValue({ ok: true, status: 200, message: "Resposta registrada." })
}));
vi.mock("next/navigation", async () => ({
  ...(await vi.importActual<typeof NextNavigation>("next/navigation")),
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn(), replace: vi.fn(), prefetch: vi.fn(), back: vi.fn(), forward: vi.fn() })
}));

import { createMessage, decideApproval, replaceTaskDependencies, scheduleExperiment, transitionTask } from "@/app/actions/critical-mutations";

import { getDefaultScreen, screens } from "@/lib/screen-catalog";
import { getWorkspaceSnapshot } from "@/lib/mock-workspace";
import { ScreenExperience } from "./screen-experience";

const playbookCodes = [
  "T02", "T03", "T09", "T12", "T18", "T19", "T22", "T24",
  "T25", "T26", "T31", "T34", "T35", "T36", "T37",
  "T39", "T41", "T43", "T46", "T49", "T50", "T51", "T52", "T53"
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

  it("binds governed search and analytics drilldown to the active workspace snapshot", () => {
    const snapshot = { ...getWorkspaceSnapshot(), currentOrganizationId: "tenant-live-42", analyticsDrilldowns: [{ card: "total" as const, dimension: "in_progress", value: 1, recordIds: ["44444444-4444-4444-8444-444444444444"], recordCount: 1, recordsTruncated: false, recordsEndpoint: "/v1/analytics/summary/records" as const, periodFrom: "2026-06-01T00:00:00Z", periodTo: "2026-07-01T00:00:00Z" }] };
    const knowledgeView = render(<ScreenExperience screen={screens.find((item) => item.code === "T38")!} snapshot={snapshot} />);
    expect(screen.getAllByText("Tenant: tenant-live-42").length).toBeGreaterThan(0);
    knowledgeView.unmount();

    render(<ScreenExperience screen={screens.find((item) => item.code === "T48")!} snapshot={snapshot} />);
    fireEvent.click(screen.getByRole("button", { name: "Status in_progress (1)" }));
    expect(screen.getByText("44444444-4444-4444-8444-444444444444")).toBeTruthy();
  });

  it("submits a room message through the server mutation boundary", async () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T11")!} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.change(screen.getByLabelText("Nova mensagem real"), { target: { value: "Contexto persistido" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar mensagem" }));
    await waitFor(() => expect(createMessage).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.getByTestId("mutation-feedback").textContent).toContain("Mensagem entregue"));
  });

  it("excludes inaccessible private rooms from the room list and counters", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T10")!} snapshot={getWorkspaceSnapshot()} />);
    const rooms = screen.getByLabelText("Salas visiveis");
    expect(within(rooms).getByText("2 salas · 3 nao lidas")).toBeTruthy();
    expect(within(rooms).getByText("Diretoria")).toBeTruthy();
    expect(within(rooms).queryByText("M&A confidencial")).toBeNull();
  });

  it("appends the next task cursor without replacing the first page", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T14")!} snapshot={getWorkspaceSnapshot()} />);
    const table = document.querySelector(".bh-data-table")!;
    expect(table.querySelectorAll(".bh-data-row")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: /Carregar proxima pagina/ }));
    expect(table.querySelectorAll(".bh-data-row")).toHaveLength(getWorkspaceSnapshot().taskMoments.length);
  });

  it("preserves transition text and presents a 409 conflict", async () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T16")!} snapshot={getWorkspaceSnapshot()} />);
    const comment = screen.getByLabelText("Motivo");
    fireEvent.change(comment, { target: { value: "Nao perder este contexto" } });
    fireEvent.click(screen.getByRole("button", { name: "Aplicar transicao" }));
    await waitFor(() => expect(transitionTask).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.getByTestId("mutation-feedback").textContent).toContain("Falha HTTP 409"));
    expect(comment).toHaveProperty("value", "Nao perder este contexto");
  });

  it("offers only valid destinations for the current task state", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T16")!} snapshot={getWorkspaceSnapshot()} />);
    const destination = screen.getByLabelText("Destino valido");
    expect(within(destination).getAllByRole("option").map((option) => option.getAttribute("value"))).toEqual(["triaged", "canceled"]);
    expect(within(destination).queryByRole("option", { name: "in_progress" })).toBeNull();
  });

  it("renders a backend dependency cycle as a dependencies field error", async () => {
    vi.mocked(replaceTaskDependencies).mockResolvedValueOnce({
      ok: false,
      status: 409,
      message: "Corrija as dependencias destacadas antes de salvar.",
      data: { fieldErrors: { dependencies: "Dependencia circular detectada." } }
    });
    render(<ScreenExperience screen={screens.find((item) => item.code === "T15")!} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.change(screen.getByLabelText("Dependencias da tarefa existente"), { target: { value: "fixture-dependent-task" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar dependencias" }));
    await waitFor(() => expect(replaceTaskDependencies).toHaveBeenCalled());
    expect((await screen.findByRole("alert")).textContent).toContain("Dependencia circular detectada.");
  });

  it("submits an approval decision through the server mutation boundary", async () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T21")!} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.click(screen.getByRole("button", { name: "Registrar decisao" }));
    await waitFor(() => expect(decideApproval).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.getByTestId("mutation-feedback").textContent).toContain("Decisao registrada"));
  });

  it("configures and starts a draft experiment through the server mutation boundary", async () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T47")!} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.click(screen.getByRole("button", { name: "Configurar e iniciar" }));
    await waitFor(() => expect(scheduleExperiment).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.getByTestId("mutation-feedback").textContent).toContain("Janela configurada"));
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

  it("preserves dashboard filters in every drill-down link", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T06")!} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.change(screen.getByLabelText("Periodo do dashboard"), { target: { value: "30d" } });
    fireEvent.change(screen.getByLabelText("Risco do dashboard"), { target: { value: "high" } });
    expect(screen.getByTestId("home-drilldown-0").getAttribute("href")).toContain("period=30d&risk=high");
  });

  it("moves keyboard focus from the command palette search to the first shortcut", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T07")!} snapshot={getWorkspaceSnapshot()} />);
    const search = screen.getByLabelText("Pesquisar no command palette");
    fireEvent.keyDown(search, { key: "ArrowDown" });
    expect(document.activeElement?.getAttribute("data-command-index")).toBe("0");
    expect(document.activeElement?.getAttribute("aria-keyshortcuts")).toBe("Alt+1");
    fireEvent.keyDown(window, { key: "1", altKey: true });
    expect(screen.getByText("Ultimo evento").parentElement?.textContent).toContain("Atalho executado:");
  });

  it("allows changing one owner and then disables removal of the last owner", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T54")!} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.click(screen.getByRole("button", { name: "Rebaixar ou remover Camila Moura" }));
    const lastOwner = screen.getByRole("button", { name: "Rebaixar ou remover Rafael Costa" });
    expect(lastOwner).toHaveProperty("disabled", true);
    expect(within(lastOwner).getByText("Ultimo owner protegido")).toBeTruthy();
  });

  it("reveals a webhook secret once and cannot reveal it again", () => {
    window.sessionStorage.clear();
    const definition = screens.find((item) => item.code === "T55")!;
    const view = render(<ScreenExperience screen={definition} snapshot={getWorkspaceSnapshot()} />);
    fireEvent.click(screen.getByRole("button", { name: "Revelar secret" }));
    expect(screen.getByTestId("webhook-secret-value").textContent).toContain("whsec_");
    fireEvent.click(screen.getByRole("button", { name: "Ocultar definitivamente" }));
    expect(screen.getByTestId("webhook-secret-value").textContent).not.toContain("whsec_");
    expect(screen.getByRole("button", { name: "Secret ja consumido" })).toHaveProperty("disabled", true);
    view.unmount();
    render(<ScreenExperience screen={definition} snapshot={getWorkspaceSnapshot()} />);
    expect(screen.getByTestId("webhook-secret-value").textContent).not.toContain("whsec_");
    expect(screen.getByRole("button", { name: "Secret ja consumido" })).toHaveProperty("disabled", true);
  });

  it("shows LGPD scope, impact and status while audit events remain read-only", () => {
    render(<ScreenExperience screen={screens.find((item) => item.code === "T56")!} snapshot={getWorkspaceSnapshot()} />);
    const jobs = screen.getByLabelText("Jobs LGPD");
    expect(within(jobs).getAllByText(/^Escopo:/)).toHaveLength(2);
    expect(within(jobs).getAllByText(/^Impacto:/)).toHaveLength(2);
    expect(within(jobs).getAllByText(/^Status:/)).toHaveLength(2);
    const audit = screen.getByLabelText("Eventos de auditoria append-only");
    expect(within(audit).queryByRole("button")).toBeNull();
    expect(within(audit).queryByText(/editar|excluir/i)).toBeTruthy();
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
