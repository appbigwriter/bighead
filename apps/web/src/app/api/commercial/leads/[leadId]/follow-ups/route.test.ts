import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedApi, getWorkspaceRequestContext } = vi.hoisted(() => ({ authenticatedApi: vi.fn(), getWorkspaceRequestContext: vi.fn() }));
vi.mock("@/lib/server-api-client", () => ({ authenticatedApi, BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } } }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext }));
import { POST } from "./route";

const leadId = "7724feab-c777-4b59-9d70-7598d40662ba";
const context = { params: Promise.resolve({ leadId }) };

describe("lead follow-up BFF", () => {
  beforeEach(() => { authenticatedApi.mockReset().mockResolvedValue({ replayed: false }); getWorkspaceRequestContext.mockReset().mockResolvedValue({ tenantId: "tenant-1" }); });
  it("forwards a normalized idempotent mutation", async () => {
    const response = await POST(new Request(`http://web.test/api/commercial/leads/${leadId}/follow-ups`, { method: "POST", headers: { origin: "http://web.test", "idempotency-key": "follow-1" }, body: JSON.stringify({ action: "Ligar", dueAt: "2030-01-01T12:00:00.000Z", notes: "Decisor" }) }), context);
    expect(response.status).toBe(201);
    expect(authenticatedApi).toHaveBeenCalledWith(`/v1/crm/leads/${leadId}/follow-ups`, expect.objectContaining({ organizationId: "tenant-1", headers: { "content-type": "application/json", "Idempotency-Key": "follow-1" } }));
  });
  it("rejects cross-origin before mutation", async () => {
    const response = await POST(new Request(`http://web.test/api/commercial/leads/${leadId}/follow-ups`, { method: "POST", headers: { origin: "https://evil.test", "idempotency-key": "follow-1" }, body: "{}" }), context);
    expect(response.status).toBe(403);
    expect(authenticatedApi).not.toHaveBeenCalled();
  });
});
