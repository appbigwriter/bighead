import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({ authenticatedApi: vi.fn(), BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } } }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { authenticatedApi } from "@/lib/server-api-client";
import { GET } from "./route";

describe("approvals BFF", () => {
  beforeEach(() => vi.mocked(authenticatedApi).mockReset().mockResolvedValue({ items: [] }));
  it("loads the approval inbox with the trusted tenant", async () => {
    expect((await GET()).status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith("/v1/approvals?queue=all", { organizationId: "tenant-cookie" });
  });
});
