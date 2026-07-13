import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatePanel } from "./state-panel";

describe("StatePanel", () => {
  it("provides universal error semantics and a reusable action slot", () => {
    render(<StatePanel action={<button>Retry</button>} kind="error" title="Falha">Tente de novo</StatePanel>);
    expect(screen.getByRole("alert").getAttribute("data-state")).toBe("error");
    expect(screen.getByRole("button", { name: "Retry" })).toBeTruthy();
  });
});
