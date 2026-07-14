import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedApi, getWorkspaceRequestContext } = vi.hoisted(() => ({ authenticatedApi: vi.fn(), getWorkspaceRequestContext: vi.fn() }));
vi.mock("@/lib/server-api-client", () => ({ authenticatedApi, BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } } }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext }));

import { GET } from "./route";

describe("commercial leads BFF", () => {
  beforeEach(() => { authenticatedApi.mockReset().mockResolvedValue({ items: [] }); getWorkspaceRequestContext.mockReset().mockResolvedValue({ tenantId: "tenant-1" }); });
  it("forwards only supported filters with the trusted tenant", async () => {
    const response = await GET(new Request("http://web.test/api/commercial/leads?stage=qualified&ownerId=user-1&ignored=x"));
    expect(response.status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/crm/leads?limit=100&stage=qualified&ownerId=user-1", { organizationId: "tenant-1" });
  });
  it("requires an active tenant", async () => {
    getWorkspaceRequestContext.mockResolvedValueOnce({});
    expect((await GET(new Request("http://web.test/api/commercial/leads"))).status).toBe(400);
  });
});
