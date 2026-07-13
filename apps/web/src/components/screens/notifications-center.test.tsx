import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedApi } = vi.hoisted(() => ({ authenticatedApi: vi.fn() }));
vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi
}));

import { NotificationsCenter } from "./notifications-center";

describe("NotificationsCenter", () => {
  beforeEach(() => authenticatedApi.mockReset());

  it("loads the real tenant feed, filters and opens supported resources", async () => {
    authenticatedApi.mockResolvedValue({
      unreadCount: 2,
      nextCursor: "next-id",
      items: [
        { id: "n-1", kind: "approval", title: "Revisar campanha", body: "Decisão vence hoje", resourceType: "approval", resourceId: "approval-7", createdAt: "2026-07-13T18:00:00Z" },
        { id: "n-2", kind: "mention", title: "Você foi mencionado", resource_type: "unknown", resource_id: "gone", read_at: "2026-07-13T18:10:00Z" }
      ]
    });
    render(await NotificationsCenter({ organizationId: "org-1", filter: "unread" }));

    expect(authenticatedApi).toHaveBeenCalledWith("/v1/notifications?filter=unread&limit=50", { organizationId: "org-1" });
    expect(screen.getByLabelText("2 notificações não lidas")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Revisar campanha/ })).toHaveAttribute("href", "/governanca/aprovacao-detalhe?approvalId=approval-7");
    expect(screen.getByText("O contexto relacionado não está mais disponível para abertura.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Não lidas" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Há mais notificações além das 50 exibidas.")).toBeTruthy();
    expect(within(screen.getByRole("list", { name: "Notificações recebidas" })).getAllByRole("listitem")).toHaveLength(2);
  });

  it("renders an actionable empty state without invented data", async () => {
    authenticatedApi.mockResolvedValue({ items: [], unreadCount: 0, nextCursor: null });
    render(await NotificationsCenter({ organizationId: "org-1", filter: "unread" }));
    expect(screen.getByText("Tudo em dia")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("keeps permission errors explicit and recoverable", async () => {
    authenticatedApi.mockImplementationOnce(() => { throw Object.assign(new Error("forbidden"), { status: 403 }); });
    render(await NotificationsCenter({ organizationId: "org-1" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Acesso não autorizado");
    expect(screen.getByRole("link", { name: "Voltar ao inÃ­cio" })).toHaveAttribute("href", "/operacao/home");
  });

  it("contains no catalog or contract copy", async () => {
    authenticatedApi.mockResolvedValue({ items: [], unreadCount: 0 });
    const view = render(await NotificationsCenter({ organizationId: "org-1" }));
    expect(view.container.textContent).not.toMatch(/T\d{2}|endpoint|fixture|OpenAPI|handoff|Sprint|contrato|QA/i);
  });
});
