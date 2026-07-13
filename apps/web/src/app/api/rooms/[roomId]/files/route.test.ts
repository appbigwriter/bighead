import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi: vi.fn(),
  BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { authenticatedApi, BigHeadApiError } from "@/lib/server-api-client";
import { GET } from "./route";

describe("room files BFF", () => {
  it.each([403, 503])("preserves upstream HTTP %i", async (status) => {
    vi.mocked(authenticatedApi).mockRejectedValueOnce(new BigHeadApiError(status, "upstream"));
    const response = await GET(new Request("http://web.test"), { params: Promise.resolve({ roomId: "room-7" }) });
    expect(response.status).toBe(status);
  });
});
