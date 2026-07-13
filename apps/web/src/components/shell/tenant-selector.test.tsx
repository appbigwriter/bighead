import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { refresh, switchTenant } = vi.hoisted(() => ({
  refresh: vi.fn(),
  switchTenant: vi.fn().mockResolvedValue({ ok: true, status: 200, message: "Organizacao alterada." })
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
vi.mock("@/app/actions/critical-mutations", () => ({ switchTenant }));

import { TenantSelector } from "./tenant-selector";

describe("TenantSelector", () => {
  it("uses the existing switch action and refreshes only after success", async () => {
    render(<TenantSelector currentOrganizationId="org-a" organizations={[{ id: "org-a", name: "Alpha" }, { id: "org-b", name: "Beta" }]} />);
    fireEvent.change(screen.getByRole("combobox", { name: "Organizacao" }), { target: { value: "org-b" } });
    fireEvent.click(screen.getByRole("button", { name: "Alternar" }));
    await waitFor(() => expect(switchTenant).toHaveBeenCalled());
    const data = switchTenant.mock.calls[0]![0] as FormData;
    expect(data.get("organizationId")).toBe("org-b");
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Organizacao alterada.")).toBeTruthy();
  });
});
