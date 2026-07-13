import { describe, expect, it, vi } from "vitest";

import {
  createHttpWorkspaceTransport,
  createWorkspaceService,
  getWorkspaceData,
  type WorkspaceTransport
} from "./workspace-service";

describe("workspace service boundary", () => {
  it("supports a genuinely asynchronous transport", async () => {
    let release!: () => void;
    const pending = new Promise<void>((resolve) => { release = resolve; });
    const original = await getWorkspaceData();
    const service = createWorkspaceService({
      getWorkspace: async () => { await pending; return { ...original, organizations: ["Tenant API"], currentOrganization: "Tenant API" }; },
      getPortal: () => Promise.reject(new Error("unused"))
    });
    let settled = false;
    const result = service.getWorkspaceData().then((value) => { settled = true; return value; });
    await Promise.resolve();
    expect(settled).toBe(false);
    release();
    await expect(result).resolves.toMatchObject({ currentOrganization: "Tenant API" });
  });

  it("propagates transport errors without converting them into fixture data", async () => {
    const transport: WorkspaceTransport = {
      getWorkspace: () => Promise.reject(new Error("API unavailable")),
      getPortal: () => Promise.reject(new Error("API unavailable"))
    };
    await expect(createWorkspaceService(transport).getWorkspaceData()).rejects.toThrow("API unavailable");
  });

  it("normalizes and rejects an invalid tenant snapshot", async () => {
    const original = await getWorkspaceData();
    const transport: WorkspaceTransport = {
      getWorkspace: () => Promise.resolve({ ...original, organizations: ["Tenant A"], currentOrganization: "Tenant B" }),
      getPortal: () => Promise.resolve({})
    };
    await expect(createWorkspaceService(transport).getWorkspaceData()).rejects.toThrow("outside the workspace");
  });

  it("keeps transport and tenant context isolated between service instances", async () => {
    const original = await getWorkspaceData();
    const seenA: Array<string | undefined> = [];
    const seenB: Array<string | undefined> = [];
    const makeTransport = (name: string, seen: Array<string | undefined>): WorkspaceTransport => ({
      getWorkspace: (context) => {
        seen.push(context?.tenantId);
        return Promise.resolve({ ...original, organizations: [name], currentOrganization: name });
      },
      getPortal: () => Promise.resolve({})
    });
    const serviceA = createWorkspaceService(makeTransport("A", seenA));
    const serviceB = createWorkspaceService(makeTransport("B", seenB));
    const [a, b] = await Promise.all([
      serviceA.getWorkspaceData({ tenantId: "tenant-a" }),
      serviceB.getWorkspaceData({ tenantId: "tenant-b" })
    ]);
    expect([a.currentOrganization, b.currentOrganization]).toEqual(["A", "B"]);
    expect(seenA).toEqual(["tenant-a"]);
    expect(seenB).toEqual(["tenant-b"]);
  });

  it("builds encoded HTTP requests with per-call tenant headers", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const transport = createHttpWorkspaceTransport({ baseUrl: "https://api.example.test/v1/", fetch: fetcher });
    await transport.getPortal("opaque/token", { tenantId: "tenant-a" });
    const [url, init] = fetcher.mock.calls[0]!;
    expect(url instanceof URL ? url.href : url).toBe("https://api.example.test/v1/portal/opaque%2Ftoken");
    expect(new Headers(init?.headers).get("x-tenant-id")).toBe("tenant-a");
  });

  it("preserves a base path without a trailing slash", async () => {
    const fetcher = vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    const transport = createHttpWorkspaceTransport({ baseUrl: "https://api.example.test/api/v1", fetch: fetcher });
    await transport.getWorkspace();
    const [url] = fetcher.mock.calls[0]!;
    expect(url instanceof URL ? url.href : url).toBe("https://api.example.test/api/v1/workspace");
  });

  it("returns isolated snapshots from the default mock transport", async () => {
    const first = await getWorkspaceData();
    first.organizations.push("Mutacao local");
    expect((await getWorkspaceData()).organizations).not.toContain("Mutacao local");
  });
});
