import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi: vi.fn(),
  BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/workspace-request-context", () => ({
  getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie-42" })
}));

import { authenticatedApi } from "@/lib/server-api-client";
import { POST } from "./route";

describe("global search BFF", () => {
  beforeEach(() => {
    vi.mocked(authenticatedApi).mockReset();
    vi.mocked(authenticatedApi).mockResolvedValue({ groups: [], shortcuts: [], removedCount: 0 });
  });

  it("uses the trusted tenant and a bounded contract payload", async () => {
    const response = await POST(new Request("http://web.test/api/search/global", {
      method: "POST",
      body: JSON.stringify({ query: "  prioridade  ", scopes: ["tasks", "secrets"] })
    }));
    expect(response.status).toBe(200);
    expect(response.headers.get("cache-control")).toBe("no-store");
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/search/global", expect.objectContaining({
      method: "POST",
      organizationId: "tenant-cookie-42",
      body: JSON.stringify({ query: "prioridade", scopes: ["tasks"], limit: 24 })
    }));
  });

  it("rejects an invalid query before calling the API", async () => {
    const response = await POST(new Request("http://web.test/api/search/global", {
      method: "POST",
      body: JSON.stringify({ query: "x", scopes: ["tasks"] })
    }));
    expect(response.status).toBe(422);
    expect(authenticatedApi).not.toHaveBeenCalled();
  });
});
