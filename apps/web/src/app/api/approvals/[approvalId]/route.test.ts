import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({ authenticatedApi: vi.fn(), BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } } }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { authenticatedApi } from "@/lib/server-api-client";
import { GET } from "./route";

const approvalId = "30000000-0000-4000-8000-000000000001";
describe("approval detail BFF", () => {
  beforeEach(() => vi.mocked(authenticatedApi).mockReset().mockResolvedValue({ approval: { id: approvalId } }));
  it("forwards a valid detail id", async () => {
    expect((await GET(new Request("http://web.test"), { params: Promise.resolve({ approvalId }) })).status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith(`/v1/approvals/${approvalId}`, { organizationId: "tenant-cookie" });
  });
  it("rejects invalid ids before the API", async () => {
    expect((await GET(new Request("http://web.test"), { params: Promise.resolve({ approvalId: "bad" }) })).status).toBe(422);
    expect(authenticatedApi).not.toHaveBeenCalled();
  });
});
