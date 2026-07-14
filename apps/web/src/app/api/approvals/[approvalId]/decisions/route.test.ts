import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({ authenticatedApi: vi.fn().mockResolvedValue({ items: [] }), BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } } }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { authenticatedApi } from "@/lib/server-api-client";
import { GET } from "./route";

const approvalId = "30000000-0000-4000-8000-000000000001";
describe("approval history BFF", () => {
  it("loads actor and timestamp history from the API", async () => {
    expect((await GET(new Request("http://web.test"), { params: Promise.resolve({ approvalId }) })).status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith(`/v1/approvals/${approvalId}/decisions`, { organizationId: "tenant-cookie" });
  });
});
