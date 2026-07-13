import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedApi, getWorkspaceRequestContext } = vi.hoisted(() => ({
  authenticatedApi: vi.fn(),
  getWorkspaceRequestContext: vi.fn()
}));

vi.mock("@/lib/server-api-client", () => ({
  authenticatedApi,
  BigHeadApiError: class BigHeadApiError extends Error {
    constructor(public status: number, message: string) { super(message); }
  }
}));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext }));

import { BigHeadApiError } from "@/lib/server-api-client";
import { POST } from "./route";

const taskId = "7724feab-c777-4b59-9d70-7598d40662ba";
const context = { params: Promise.resolve({ taskId }) };

function request(body: Record<string, unknown>, origin = "http://web.test") {
  return new Request(`http://web.test/api/tasks/${taskId}/transition`, {
    method: "POST",
    headers: { origin, "content-type": "application/json" },
    body: JSON.stringify(body)
  });
}

describe("task transition BFF", () => {
  beforeEach(() => {
    getWorkspaceRequestContext.mockReset().mockResolvedValue({ tenantId: "tenant-cookie-42" });
    authenticatedApi.mockReset().mockResolvedValue({ task: { id: taskId, version: 2, status: "triaged" } });
  });

  it("derives the organization from the trusted cookie context and forwards a validated payload", async () => {
    const response = await POST(request({
      organizationId: "attacker-tenant",
      targetState: "triaged",
      expectedVersion: 1,
      reason: "Validacao BFF"
    }), context);

    expect(response.status).toBe(200);
    expect(authenticatedApi).toHaveBeenCalledWith(`/v1/tasks/${taskId}/transition`, {
      method: "POST",
      organizationId: "tenant-cookie-42",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ targetState: "triaged", expectedVersion: 1, reason: "Validacao BFF" })
    });
  });

  it("rejects cross-origin and malformed requests before accessing the authenticated API", async () => {
    expect((await POST(request({ targetState: "triaged", expectedVersion: 1 }, "https://evil.test"), context)).status).toBe(403);
    expect((await POST(request({ targetState: "unknown", expectedVersion: 0 }), context)).status).toBe(422);
    expect(authenticatedApi).not.toHaveBeenCalled();
  });

  it("requires an active cookie tenant and preserves authentication failures", async () => {
    getWorkspaceRequestContext.mockResolvedValueOnce({});
    expect((await POST(request({ targetState: "triaged", expectedVersion: 1 }), context)).status).toBe(400);

    authenticatedApi.mockRejectedValueOnce(new BigHeadApiError(401, "Sessao invalida"));
    const response = await POST(request({ targetState: "triaged", expectedVersion: 1 }), context);
    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({
      ok: false,
      status: 401,
      message: "Sua sessao expirou. Entre novamente."
    });
  });
});
