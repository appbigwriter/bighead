import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/app/actions/critical-mutations", () => ({
  decidePortal: vi.fn().mockResolvedValue({ ok: true, status: 200, message: "Resposta externa registrada e auditada." })
}));

import { decidePortal } from "@/app/actions/critical-mutations";
import { PortalExperience } from "./portal-experience";

describe("PortalExperience", () => {
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
