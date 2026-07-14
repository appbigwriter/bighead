import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi: vi.fn(),
  BigHeadApiError: class BigHeadApiError extends Error { constructor(public status: number, message: string) { super(message); } }
}));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: vi.fn().mockResolvedValue({ tenantId: "tenant-cookie" }) }));

import { authenticatedApi } from "@/lib/server-api-client";
import { GET } from "./route";

describe("task detail BFF", () => {
  beforeEach(() => vi.mocked(authenticatedApi).mockReset());

  it("loads the exact task under the active tenant", async () => {
    const taskId = "22222222-2222-4222-8222-222222222222";
    vi.mocked(authenticatedApi).mockResolvedValue({ id: taskId, title: "Selecionada" });
    const response = await GET(new Request(`http://web.test/api/tasks/${taskId}`), { params: Promise.resolve({ taskId }) });
    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({ id: taskId, title: "Selecionada" });
    expect(authenticatedApi).toHaveBeenCalledWith(`/v1/tasks/${taskId}`, { organizationId: "tenant-cookie" });
  });

  it("rejects an invalid task id before calling the API", async () => {
    const response = await GET(new Request("http://web.test/api/tasks/not-a-task"), { params: Promise.resolve({ taskId: "not-a-task" }) });
    expect(response.status).toBe(422);
    expect(authenticatedApi).not.toHaveBeenCalled();
  });
});
