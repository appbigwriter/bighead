import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedApi, ApiError } = vi.hoisted(() => ({
  authenticatedApi: vi.fn(), ApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/server-api-client", () => ({ authenticatedApi, BigHeadApiError: ApiError }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { POST } from "./route";
const approvalId = "30000000-0000-4000-8000-000000000001";

describe("approval decision BFF", () => {
  beforeEach(() => authenticatedApi.mockReset().mockResolvedValue({ roundResult: "approved" }));
  it("forwards the decision and expected round under the trusted tenant", async () => {
    const response = await POST(new Request("http://web.test/api/approvals/x/decision", { method: "POST", headers: { origin: "http://web.test" }, body: JSON.stringify({ decision: "approved", expectedRound: 2, comment: "Revisado" }) }), { params: Promise.resolve({ approvalId }) });
    expect(response.status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith(`/v1/approvals/${approvalId}/decision`, expect.objectContaining({ organizationId: "tenant-cookie", body: JSON.stringify({ decision: "approved", expectedRound: 2, comment: "Revisado" }) }));
  });
  it("preserves API semantics for self-approval and concurrent decisions", async () => {
    for (const status of [403, 409]) {
      authenticatedApi.mockRejectedValueOnce(new ApiError(status, "blocked"));
      const response = await POST(new Request("http://web.test/api/approvals/x/decision", { method: "POST", headers: { origin: "http://web.test" }, body: JSON.stringify({ decision: "rejected", expectedRound: 2 }) }), { params: Promise.resolve({ approvalId }) });
      expect(response.status).toBe(status);
    }
  });
});
