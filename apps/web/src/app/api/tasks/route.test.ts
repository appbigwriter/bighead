import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({ authenticatedApi: vi.fn(), BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } } }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { authenticatedApi } from "@/lib/server-api-client";
import { GET, POST } from "./route";

describe("tasks BFF", () => {
  beforeEach(() => vi.mocked(authenticatedApi).mockReset().mockResolvedValue({ items: [], nextCursor: null }));

  it("forwards the supported task filters", async () => {
    expect((await GET(new Request("http://web.test/api/tasks?status=triaged&ownerId=user-1&risk=high&slaStatus=overdue&roomId=room-7&ignored=no"))).status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/tasks?limit=100&status=triaged&ownerId=user-1&risk=high&slaStatus=overdue&roomId=room-7", { organizationId: "tenant-cookie" });
  });

  it("creates with trusted tenant, context IDs and idempotency", async () => {
    const response = await POST(new Request("http://web.test/api/tasks", {
      method: "POST", headers: { origin: "http://web.test", "idempotency-key": "task-key" },
      body: JSON.stringify({ goal: "Executar entrega", roomId: "room-1", sourceMessageId: "message-1", risk: "high" })
    }));
    expect(response.status).toBe(201);
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/tasks", expect.objectContaining({
      organizationId: "tenant-cookie",
      headers: { "content-type": "application/json", "Idempotency-Key": "task-key" },
      body: JSON.stringify({ goal: "Executar entrega", title: null, risk: "high", roomId: "room-1", sourceMessageId: "message-1", slaAt: null, dependencies: [] })
    }));
  });
});
