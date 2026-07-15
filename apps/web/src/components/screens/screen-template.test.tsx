import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { getServerWorkspaceData, getWorkspaceRequestContext } = vi.hoisted(() => ({
  getServerWorkspaceData: vi.fn(),
  getWorkspaceRequestContext: vi.fn()
}));

vi.mock("@/lib/server-workspace-service", () => ({ getServerWorkspaceData }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext }));
vi.mock("./screen-experience", () => ({
  ScreenExperience: ({ screen }: { screen: { title: string } }) => <div>Screen experience: {screen.title}</div>
}));

vi.mock("./domain-workspace", () => ({
  DomainWorkspace: ({ screen }: { screen: { title: string } }) => <div>Product domain: {screen.title}</div>
}));

vi.mock("./notifications-center", () => ({
  NotificationsCenter: ({ filter }: { filter: string }) => <div>Product notifications: {filter}</div>
}));
vi.mock("./conversations-workspace", () => ({
  ConversationsWorkspace: ({ mode }: { mode: string }) => <div>Product conversations: {mode}</div>
}));
vi.mock("./tasks-workspace", () => ({
  TasksWorkspace: ({ mode }: { mode: string }) => <div>Product tasks: {mode}</div>
}));
vi.mock("./commercial-workspace", () => ({
  CommercialWorkspace: ({ mode }: { mode: string }) => <div>Product commercial: {mode}</div>
}));

import { getWorkspaceSnapshot } from "@/lib/mock-workspace";
import { getDefaultScreen } from "@/lib/screen-catalog";

import { ScreenTemplate } from "./screen-template";

describe("ScreenTemplate product routing", () => {
  beforeEach(() => {
    getWorkspaceRequestContext.mockReset().mockResolvedValue({ tenantId: "org-1" });
    getServerWorkspaceData.mockReset().mockResolvedValue(getWorkspaceSnapshot());
  });

  it("selects the product Home for /operacao/home", async () => {
    render(await ScreenTemplate({ screen: getDefaultScreen() }));

    expect(screen.getByRole("heading", { name: /Operação de Acme Growth/ })).toBeTruthy();
    expect(screen.queryByText("Home operacional")).toBeNull();
  });

  it("selects product search without loading the workspace snapshot", async () => {
    const searchScreen = { ...getDefaultScreen(), slug: ["operacao", "busca-global"] };

    render(await ScreenTemplate({ screen: searchScreen }));

    expect(screen.getByRole("heading", { name: "Encontre trabalho e contexto" })).toBeTruthy();
    expect(getServerWorkspaceData).not.toHaveBeenCalled();
  });

  it("selects product notifications and keeps the URL filter", async () => {
    const notificationsScreen = { ...getDefaultScreen(), slug: ["operacao", "notificacoes"] };

    render(await ScreenTemplate({ screen: notificationsScreen, searchParams: { filter: "unread" } }));

    expect(screen.getByText("Product notifications: unread")).toBeTruthy();
  });

  it.each([
    [["colaboracao", "salas"], "list"],
    [["colaboracao", "sala"], "room"]
  ] as const)("selects product conversations for %s", async (slug, mode) => {
    const conversationScreen = { ...getDefaultScreen(), slug: [...slug] };

    render(await ScreenTemplate({ screen: conversationScreen }));

    expect(screen.getByText(`Product conversations: ${mode}`)).toBeTruthy();
    expect(getServerWorkspaceData).not.toHaveBeenCalled();
  });

  it.each([
    [["tarefas", "inbox"], "inbox"],
    [["tarefas", "criar"], "create"],
    [["tarefas", "detalhe"], "detail"]
  ] as const)("selects product tasks for %s", async (slug, mode) => {
    const taskScreen = { ...getDefaultScreen(), slug: [...slug] };

    render(await ScreenTemplate({ screen: taskScreen }));

    expect(screen.getByText(`Product tasks: ${mode}`)).toBeTruthy();
    expect(getServerWorkspaceData).not.toHaveBeenCalled();
  });

  it.each([
    [["comercial", "leads"], "leads"],
    [["comercial", "lead-detalhe"], "detail"],
    [["comercial", "pipeline"], "pipeline"]
  ] as const)("selects product commercial for %s", async (slug, mode) => {
    const commercialScreen = { ...getDefaultScreen(), slug: [...slug] };
    render(await ScreenTemplate({ screen: commercialScreen }));
    expect(screen.getByText(`Product commercial: ${mode}`)).toBeTruthy();
    expect(getServerWorkspaceData).not.toHaveBeenCalled();
  });

  it("selects ScreenExperience instead of DomainWorkspace for non-specialized routes", async () => {
    const fallbackScreen = { ...getDefaultScreen(), title: "Biblioteca de conhecimento", slug: ["conhecimento", "biblioteca"] };

    render(await ScreenTemplate({ screen: fallbackScreen }));

    expect(screen.getByText("Screen experience: Biblioteca de conhecimento")).toBeTruthy();
    expect(screen.queryByText("Product domain: Biblioteca de conhecimento")).toBeNull();
    expect(getServerWorkspaceData).toHaveBeenCalledOnce();
  });
});
