import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi: vi.fn(),
  BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { authenticatedApi } from "@/lib/server-api-client";
import { GET, POST } from "./route";

describe("rooms BFF", () => {
  beforeEach(() => vi.mocked(authenticatedApi).mockReset());

  it("lists rooms using the trusted tenant", async () => {
    vi.mocked(authenticatedApi).mockResolvedValue({ rooms: [], counters: { total: 0 } });
    expect((await GET()).status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/rooms?limit=100", { organizationId: "tenant-cookie" });
  });

  it("creates a room with the contracted payload", async () => {
    vi.mocked(authenticatedApi).mockResolvedValue({ id: "room-1", name: "Operação" });
    const response = await POST(new Request("http://web.test/api/rooms", { method: "POST", body: JSON.stringify({ name: " Operação ", description: " Time ", isPrivate: true }) }));
    expect(response.status).toBe(201);
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/rooms", expect.objectContaining({
      organizationId: "tenant-cookie",
      body: JSON.stringify({ name: "Operação", description: "Time", isPrivate: true })
    }));
  });
});
