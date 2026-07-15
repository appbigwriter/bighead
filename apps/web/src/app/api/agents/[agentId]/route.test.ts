import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ authenticatedApi: vi.fn(), getContext: vi.fn() }));
vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi: mocks.authenticatedApi,
  BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: mocks.getContext }));

import { DELETE, GET, PATCH } from "./route";

const agentId = "11111111-1111-4111-8111-111111111111";
const route = { params: Promise.resolve({ agentId }) };

describe("/api/agents/[agentId]", () => {
  beforeEach(() => {
    mocks.authenticatedApi.mockReset().mockResolvedValue({ agent: { id: agentId }, versions: [] });
    mocks.getContext.mockReset().mockResolvedValue({ tenantId: "tenant-1" });
  });

  it("loads the exact agent", async () => {
    expect((await GET(new Request("http://web.test"), route)).status).toBe(200);
    expect(mocks.authenticatedApi).toHaveBeenCalledWith(`/v1/agents/${agentId}`, { organizationId: "tenant-1" });
  });

  it("patches configuration with optimistic version", async () => {
    const response = await PATCH(new Request(`http://web.test/api/agents/${agentId}`, {
      method: "PATCH", headers: { origin: "http://web.test", "content-type": "application/json" },
      body: JSON.stringify({ name: "SDR 2", description: "Atualizado", riskLevel: "high", prompt: "Novo prompt", isEnabled: true, expectedVersion: 2, limits: { maxTokens: 1000 }, skillIds: [] })
    }), route);
    expect(response.status).toBe(200);
    expect(mocks.authenticatedApi).toHaveBeenCalledWith(`/v1/agents/${agentId}`, expect.objectContaining({
      method: "PATCH", organizationId: "tenant-1",
      body: JSON.stringify({ name: "SDR 2", description: "Atualizado", riskLevel: "high", isEnabled: true, prompt: "Novo prompt", modelId: null, limits: { maxTokens: 1000 }, skillIds: [], expectedVersion: 2 })
    }));
  });

  it("archives through DELETE", async () => {
    mocks.authenticatedApi.mockResolvedValue(undefined);
    const response = await DELETE(new Request(`http://web.test/api/agents/${agentId}?expectedVersion=2`, { method: "DELETE", headers: { origin: "http://web.test" } }), route);
    expect(response.status).toBe(204);
    expect(mocks.authenticatedApi).toHaveBeenCalledWith(`/v1/agents/${agentId}?expectedVersion=2`, { method: "DELETE", organizationId: "tenant-1" });
  });

  it("rejects invalid ids and versions", async () => {
    expect((await GET(new Request("http://web.test"), { params: Promise.resolve({ agentId: "bad" }) })).status).toBe(422);
    expect((await PATCH(new Request(`http://web.test/api/agents/${agentId}`, { method: "PATCH", headers: { origin: "http://web.test" }, body: "{}" }), route)).status).toBe(422);
    expect(mocks.authenticatedApi).not.toHaveBeenCalled();
  });
});
