import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ authenticatedApi: vi.fn(), getContext: vi.fn() }));
vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi: mocks.authenticatedApi,
  BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: mocks.getContext }));

import { GET, POST } from "./route";

describe("/api/agents", () => {
  beforeEach(() => {
    mocks.authenticatedApi.mockReset(); mocks.getContext.mockReset().mockResolvedValue({ tenantId: "tenant-1" });
  });

  it("lists agents in the active tenant", async () => {
    mocks.authenticatedApi.mockResolvedValue({ items: [] });
    const response = await GET();
    expect(response.status).toBe(200);
    expect(mocks.authenticatedApi).toHaveBeenCalledWith("/v1/agents", { organizationId: "tenant-1" });
    expect(response.headers.get("cache-control")).toBe("no-store");
  });

  it("creates a normalized agent", async () => {
    mocks.authenticatedApi.mockResolvedValue({ agent: { id: "agent-1" } });
    const response = await POST(new Request("http://web.test/api/agents", {
      method: "POST", headers: { origin: "http://web.test", "content-type": "application/json" },
      body: JSON.stringify({ name: "SDR", slug: "sdr-agent", prompt: "Prospecte", riskLevel: "high", skillIds: ["skill-1"] })
    }));
    expect(response.status).toBe(201);
    expect(mocks.authenticatedApi).toHaveBeenCalledWith("/v1/agents", expect.objectContaining({
      method: "POST", organizationId: "tenant-1",
      body: JSON.stringify({ name: "SDR", slug: "sdr-agent", description: null, riskLevel: "high", prompt: "Prospecte", modelId: null, limits: {}, skillIds: ["skill-1"] })
    }));
  });

  it("rejects cross-site and invalid creation before the API", async () => {
    expect((await POST(new Request("http://web.test/api/agents", { method: "POST", headers: { origin: "https://evil.test" }, body: "{}" }))).status).toBe(403);
    expect((await POST(new Request("http://web.test/api/agents", { method: "POST", headers: { origin: "http://web.test" }, body: "{}" }))).status).toBe(422);
    expect(mocks.authenticatedApi).not.toHaveBeenCalled();
  });
});
