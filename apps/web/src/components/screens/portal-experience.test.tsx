import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/app/actions/critical-mutations", () => ({
  decidePortal: vi.fn().mockResolvedValue({ ok: true, status: 200, message: "Resposta externa registrada e auditada." })
}));

import { decidePortal } from "@/app/actions/critical-mutations";
import { PortalExperience } from "./portal-experience";

describe("PortalExperience", () => {
  it("renders the allowlisted public experience without workspace shell or leaked internal data", () => {
    const preview = {
      token: "opaque-token", state: "valid" as const, title: "Revisao externa", summary: "Escopo publico",
      requestedBy: "Equipe", dueLabel: "Hoje", allowedActions: ["approve"],
      guardRails: ["isolado"], expectedRound: 2,
      organizations: ["Tenant Secret"], analytics: "R$ secret", internalUrl: "https://internal.invalid"
    };
    const { container } = render(<PortalExperience preview={preview} />);
    expect(container.querySelector(".bh-shell")).not.toBeInTheDocument();
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(screen.queryByText("Tenant Secret")).not.toBeInTheDocument();
    expect(screen.queryByText("R$ secret")).not.toBeInTheDocument();
    expect(screen.queryByText("https://internal.invalid")).not.toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveClass("bh-portal");
  });

  it("submits comment and decision through the public server action", async () => {
    render(<PortalExperience preview={{
      token: "opaque-token", state: "valid", title: "Revisao", summary: "Escopo",
      requestedBy: "Equipe", dueLabel: "Hoje", allowedActions: ["approve"],
      guardRails: ["isolado"], expectedRound: 2
    }} />);
    fireEvent.click(screen.getByRole("button", { name: "approved" }));
    fireEvent.change(screen.getByLabelText("Comentario externo"), { target: { value: "Aprovado pela UI" } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar resposta" }));
    await waitFor(() => expect(decidePortal).toHaveBeenCalledOnce());
    await waitFor(() => expect(screen.getByRole("status").textContent).toContain("Resposta externa registrada"));
  });
});
