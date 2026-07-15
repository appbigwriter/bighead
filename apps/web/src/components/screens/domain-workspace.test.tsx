import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { getWorkspaceSnapshot } from "@/lib/mock-workspace";
import { screens } from "@/lib/screen-catalog";
import { DomainWorkspace } from "./domain-workspace";

describe("DomainWorkspace", () => {
  it("renders useful domain context without QA scaffolding", () => {
    const definition = screens.find((item) => item.slug.join("/") === "conhecimento/biblioteca")!;
    const view = render(<DomainWorkspace screen={definition} snapshot={getWorkspaceSnapshot()} />);

    expect(screen.getByRole("heading", { name: definition.title })).toBeTruthy();
    expect(screen.getByText("Acme Growth")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Fontes e memoria" })).toBeTruthy();
    expect(screen.getByRole("navigation", { name: "Destinos de Conhecimento" })).toBeTruthy();
    expect(view.container.textContent).not.toMatch(/T\d{2}|GET \/v1|POST \/v1|estado simulado|checklist|ultimo evento|abrir catalogo/i);
  });

  it("lets the admin area create invites, edit roles and register executor teams", () => {
    const definition = screens.find((item) => item.slug.join("/") === "administracao/membros")!;
    render(<DomainWorkspace screen={definition} snapshot={getWorkspaceSnapshot()} />);

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "novo@acme.ai" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar convite" }));
    fireEvent.change(screen.getByLabelText("Papel de Camila Moura"), { target: { value: "admin" } });
    fireEvent.change(screen.getByLabelText("Nome do time"), { target: { value: "Time Growth" } });
    fireEvent.change(screen.getByLabelText("Executor ID"), { target: { value: "team-growth" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvar time" }));

    expect(screen.getByText("novo@acme.ai")).toBeTruthy();
    expect(screen.getByText("Time Growth")).toBeTruthy();
    expect(screen.getByLabelText("Papel de Camila Moura")).toHaveValue("admin");
    expect(screen.getAllByRole("button", { name: "Excluir" })).toHaveLength(3);
  });

  it.each(["Acesso", "Operacao", "Governanca", "Automacao", "Conhecimento", "Comercial", "Aprendizado", "Administracao"] as const)(
    "keeps a useful workspace available for %s routes",
    (area) => {
      const definition = screens.find((item) => item.area === area)!;
      render(<DomainWorkspace screen={definition} snapshot={getWorkspaceSnapshot()} />);

      expect(screen.getByRole("heading", { name: definition.title })).toBeTruthy();
      expect(screen.getByRole("navigation", { name: `Destinos de ${area}` })).toBeTruthy();
    }
  );
});
