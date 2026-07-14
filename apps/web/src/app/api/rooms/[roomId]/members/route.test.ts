import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi: vi.fn(),
  BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { authenticatedApi } from "@/lib/server-api-client";
import { GET } from "./route";

describe("room members BFF", () => {
  it("loads members under the active tenant", async () => {
    vi.mocked(authenticatedApi).mockResolvedValue({ room: { id: "room-7" }, members: [{ userId: "user-1", isModerator: true }] });
    const response = await GET(new Request("http://web.test/api/rooms/room-7/members"), { params: Promise.resolve({ roomId: "room-7" }) });
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ members: [{ userId: "user-1", isModerator: true }] });
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/rooms/room-7/members", { organizationId: "tenant-cookie" });
  });
});
