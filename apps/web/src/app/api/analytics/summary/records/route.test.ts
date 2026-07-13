import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi: vi.fn(),
  BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/workspace-request-context", () => ({
  getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie-42" })
}));

import { authenticatedApi } from "@/lib/server-api-client";
import { GET } from "./route";

describe("analytics records BFF", () => {
  beforeEach(() => vi.mocked(authenticatedApi).mockResolvedValue({ items: [], total: 0, nextCursor: null }));

  it("forwards tenant, dimension, period and cursor through the authenticated server client", async () => {
    const response = await GET(new Request("http://web.test/api/analytics/summary/records?organizationId=attacker-tenant&dimension=in_progress&from=2026-06-01T00%3A00%3A00Z&to=2026-07-01T00%3A00%3A00Z&cursor=next-1"));
    expect(response.status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith(
      "/v1/analytics/summary/records?dimension=in_progress&limit=100&from=2026-06-01T00%3A00%3A00Z&to=2026-07-01T00%3A00%3A00Z&cursor=next-1",
      { organizationId: "tenant-cookie-42" }
    );
  });
});
