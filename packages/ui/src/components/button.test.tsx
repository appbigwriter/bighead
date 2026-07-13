import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./button";

describe("Button", () => {
  it("renders children", () => {
    render(<Button>Executar</Button>);
    expect(screen.getByRole("button", { name: "Executar" })).toBeTruthy();
  });
});
