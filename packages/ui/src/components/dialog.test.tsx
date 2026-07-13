import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Dialog } from "./dialog";

describe("Dialog", () => {
  it("binds each native dialog to its own accessible title", () => {
    render(<><Dialog open title="Confirmar">Primeiro</Dialog><Dialog open title="Excluir">Segundo</Dialog></>);
    const dialogs = screen.getAllByRole("dialog");
    expect(dialogs.map((item) => item.getAttribute("aria-labelledby"))).toHaveLength(2);
    expect(new Set(dialogs.map((item) => item.getAttribute("aria-labelledby"))).size).toBe(2);
  });
});
