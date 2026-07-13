import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({ usePathname: () => "/tarefas/inbox", useRouter: () => ({ refresh: vi.fn() }) }));
vi.mock("@/app/actions/critical-mutations", () => ({ switchTenant: vi.fn() }));

import { WorkspaceNavigation } from "./workspace-navigation";
import { primaryNavigation } from "./workspace-navigation-config";

const more = [{ label: "Administracao", routes: [{ label: "Integracoes", href: "/administracao/integracoes" }] }];

describe("WorkspaceNavigation", () => {
  const props = {
    currentOrganizationId: "org-atlas",
    more,
    organizations: [{ id: "org-atlas", name: "Atlas" }, { id: "org-north", name: "North" }],
    primary: primaryNavigation,
    tenantCount: 2,
    tenantName: "Atlas"
  };

  it("traps focus, isolates the workspace and restores focus when the drawer closes", () => {
    render(<><WorkspaceNavigation {...props} /><main id="workspace-content"><button type="button">Acao de fundo</button></main></>);
    const menu = screen.getByRole("button", { name: "Menu" });
    expect(menu.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(menu);
    expect(menu.getAttribute("aria-expanded")).toBe("true");
    const dialog = screen.getByRole("dialog", { name: "Navegacao do workspace" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    const close = screen.getByRole("button", { name: "Fechar menu" });
    const first = screen.getByRole("link", { name: /BigHead Operacoes/ });
    const last = screen.getByText("Mais");
    expect(close).toHaveFocus();
    expect(document.getElementById("workspace-content")).toHaveAttribute("inert");
    expect(document.getElementById("workspace-content")).toHaveAttribute("aria-hidden", "true");
    first.focus();
    fireEvent.keyDown(window, { key: "Tab", shiftKey: true });
    expect(last).toHaveFocus();
    fireEvent.keyDown(window, { key: "Tab" });
    expect(first).toHaveFocus();
    fireEvent.keyDown(window, { key: "Escape" });
    expect(menu.getAttribute("aria-expanded")).toBe("false");
    expect(menu).toHaveFocus();
    expect(document.getElementById("workspace-content")).not.toHaveAttribute("inert");
    expect(document.getElementById("workspace-content")).not.toHaveAttribute("aria-hidden");
  });

  it("marks the current route and exposes the tenant selector and collapsed deep links", () => {
    render(<WorkspaceNavigation {...props} />);
    expect(screen.getByRole("link", { name: "Tarefas" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("combobox", { name: "Organizacao" })).toHaveValue("org-atlas");
    expect(screen.getByRole("button", { name: "Alternar" })).toBeTruthy();
    expect(screen.getByText("Mais")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Integracoes" })).toBeTruthy();
  });
});
