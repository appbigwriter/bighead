import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi: vi.fn(),
  BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { authenticatedApi } from "@/lib/server-api-client";
import { POST } from "./route";

describe("messages BFF", () => {
  it("persists clientId and returns the reconciliation projection", async () => {
    vi.mocked(authenticatedApi).mockResolvedValue({ id: "message-1", roomId: "room-7", authorUserId: "user-1", body: "Olá", metadata: { client_id: "client-9" }, createdAt: "2026-07-13T12:00:00Z" });
    const response = await POST(
      new Request("http://web.test/api/rooms/room-7/messages", { method: "POST", body: JSON.stringify({ body: "Olá", clientId: "client-9" }) }),
      { params: Promise.resolve({ roomId: "room-7" }) }
    );
    expect(response.status).toBe(201);
    expect(await response.json()).toMatchObject({ id: "message-1", roomId: "room-7", clientId: "client-9", body: "Olá" });
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/rooms/room-7/messages", expect.objectContaining({
      organizationId: "tenant-cookie",
      body: JSON.stringify({ body: "Olá", clientId: "client-9" })
    }));
  });
});
