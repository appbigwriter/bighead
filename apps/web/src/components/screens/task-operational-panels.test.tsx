import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TaskOperationalPanels } from "./task-operational-panels";

describe("TaskOperationalPanels", () => {
  it("paginates logs and costs independently without blocking task detail", () => {
    render(<TaskOperationalPanels taskTitle="BH-1842" />);
    const logs = screen.getByRole("region", { name: "Logs paginados" });
    const costs = screen.getByRole("region", { name: "Custos paginados" });
    expect(screen.getByTestId("task-detail-summary")).toHaveTextContent("BH-1842");
    fireEvent.click(within(logs).getByRole("button", { name: "Proxima pagina de logs" }));
    expect(within(logs).getByText("Logs · pagina 2")).toBeTruthy();
    expect(within(costs).getByText("Custos · pagina 1")).toBeTruthy();
    fireEvent.click(within(costs).getByRole("button", { name: "Proxima pagina de custos" }));
    expect(within(costs).getByText("Custos · pagina 2")).toBeTruthy();
    expect(screen.getByTestId("task-detail-summary")).toBeTruthy();
  });
});
