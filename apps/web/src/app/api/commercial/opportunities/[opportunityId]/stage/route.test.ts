import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedApi, getWorkspaceRequestContext } = vi.hoisted(() => ({ authenticatedApi: vi.fn(), getWorkspaceRequestContext: vi.fn() }));
vi.mock("@/lib/server-api-client", () => ({ authenticatedApi, BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } } }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext }));
import { POST } from "./route";

const opportunityId = "7724feab-c777-4b59-9d70-7598d40662ba";
const context = { params: Promise.resolve({ opportunityId }) };

describe("opportunity stage BFF", () => {
  beforeEach(() => { authenticatedApi.mockReset().mockResolvedValue({ opportunity: { stage: "negotiation" } }); getWorkspaceRequestContext.mockReset().mockResolvedValue({ tenantId: "tenant-1" }); });
  it("uses trusted tenant and forwards conditional fields", async () => {
    const response = await POST(new Request(`http://web.test/api/commercial/opportunities/${opportunityId}/stage`, { method: "POST", headers: { origin: "http://web.test" }, body: JSON.stringify({ targetStage: "negotiation", amount: "1200", probability: "60", expectedCloseDate: "2030-02-03" }) }), context);
    expect(response.status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith(`/v1/crm/opportunities/${opportunityId}/stage`, expect.objectContaining({ organizationId: "tenant-1", body: JSON.stringify({ targetStage: "negotiation", amount: 1200, probability: 60, expectedCloseDate: "2030-02-03", lossReason: null, requiredFields: {}, forecast: {} }) }));
  });
});
