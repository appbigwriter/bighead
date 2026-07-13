import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TransverseStateCatalog } from "./transverse-state-catalog";
import { transverseStates } from "./transverse-states";

describe("transverseStates", () => {
  it("documents every required reusable state with actionable copy", () => {
    expect(transverseStates.map((state) => state.name)).toEqual([
      "Loading", "Vazio", "Erro", "Sem permissao", "Offline", "Sucesso"
    ]);
    expect(transverseStates.every((state) => state.description.length >= 20)).toBe(true);

    render(<TransverseStateCatalog />);
    for (const state of transverseStates) {
      expect(screen.getByText(state.name)).toBeTruthy();
      expect(screen.getByText(state.description)).toBeTruthy();
    }
    expect(screen.getByTestId("loading-skeleton")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Criar primeiro item" })).toBeTruthy();
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByTestId("permission-state").querySelector("button")).toBeNull();
    expect(screen.getByRole("button", { name: "Reconectar" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Continuar" })).toBeTruthy();
    expect(document.querySelectorAll('[data-responsive="desktop mobile"]')).toHaveLength(6);
    expect(document.querySelectorAll('[data-state]')).toHaveLength(6);
    for (const control of [...screen.getAllByRole("button"), ...screen.getAllByRole("link")]) {
      expect(control.tabIndex).toBeGreaterThanOrEqual(0);
      control.focus();
      expect(document.activeElement).toBe(control);
    }
  });
});
