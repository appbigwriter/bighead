import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { saveVisualPreferences } = vi.hoisted(() => ({ saveVisualPreferences: vi.fn().mockResolvedValue(undefined) }));
vi.mock("@/app/actions/visual-preferences", () => ({ saveVisualPreferences }));
import { ThemeToggle } from "./theme-toggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    saveVisualPreferences.mockClear();
    localStorage.clear();
    document.documentElement.dataset.theme = "aurora-light";
    document.documentElement.dataset.density = "comfortable";
    document.documentElement.dataset.motion = "full";
  });

  it("applies preferences synchronously and then persists them through the API", async () => {
    render(<ThemeToggle organizationId="org-1" />);
    fireEvent.click(screen.getByRole("button", { name: "Alternar densidade" }));
    expect(document.documentElement.dataset.density).toBe("compact");
    expect(localStorage.getItem("bighead-visual-preferences")).toContain('"density":"compact"');
    await waitFor(() => expect(saveVisualPreferences).toHaveBeenCalledWith(expect.objectContaining({ organizationId: "org-1", density: "compact" })));
  });
});
