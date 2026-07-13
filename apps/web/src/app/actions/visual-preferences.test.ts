import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedApi } = vi.hoisted(() => ({ authenticatedApi: vi.fn() }));
vi.mock("@/lib/server-api-client", () => ({ authenticatedApi }));

import { saveVisualPreferences } from "./visual-preferences";

describe("saveVisualPreferences", () => {
  beforeEach(() => authenticatedApi.mockReset().mockResolvedValue({}));

  it("synchronizes every visual preference through the stable API contract", async () => {
    await saveVisualPreferences({ organizationId: "org-1", theme: "radar-dark", density: "compact", motion: "reduced" });
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/preferences", expect.objectContaining({
      method: "PATCH",
      organizationId: "org-1",
      body: JSON.stringify({ theme: "dark", accessibility: { density: "compact", reducedMotion: true } })
    }));
  });
});
