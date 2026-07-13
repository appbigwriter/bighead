import { describe, expect, it, vi } from "vitest";

import {
  createHttpWorkspaceTransport,
  createAuthenticatedWorkspaceTransport,
  createWorkspaceService,
  fixtureWorkspaceService,
  normalizePortalPreview,
  type WorkspaceTransport
} from "./workspace-service";
import type { WorkspaceHttpError } from "./workspace-service";

describe("workspace service boundary", () => {
  it("supports a genuinely asynchronous transport", async () => {
    let release!: () => void;
    const pending = new Promise<void>((resolve) => { release = resolve; });
    const original = await fixtureWorkspaceService.getWorkspaceData();
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
    const original = await fixtureWorkspaceService.getWorkspaceData();
    const transport: WorkspaceTransport = {
      getWorkspace: () => Promise.resolve({ ...original, organizations: ["Tenant A"], currentOrganization: "Tenant B" }),
      getPortal: () => Promise.resolve({})
    };
    await expect(createWorkspaceService(transport).getWorkspaceData()).rejects.toThrow("outside the workspace");
  });

  it("keeps transport and tenant context isolated between service instances", async () => {
    const original = await fixtureWorkspaceService.getWorkspaceData();
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
    const first = await fixtureWorkspaceService.getWorkspaceData();
    first.organizations.push("Mutacao local");
    expect((await fixtureWorkspaceService.getWorkspaceData()).organizations).not.toContain("Mutacao local");
  });

  it("uses the supplied session token and never performs credential login", async () => {
    const paths: string[] = [];
    const fetcher = vi.fn<typeof fetch>((input, init) => {
      const inputUrl = typeof input === "string" || input instanceof URL ? input : input.url;
      const path = new URL(inputUrl).pathname;
      paths.push(path);
      const headers = new Headers(init?.headers);
      expect(headers.get("authorization")).toBe("Bearer session-jwt");
      if (path.endsWith("/organizations")) {
        return Promise.resolve(new Response(JSON.stringify({ organizations: [{ id: "tenant-a", name: "Tenant A" }] })));
      }
      return Promise.resolve(new Response(JSON.stringify(
        path.endsWith("/rooms") ? { rooms: [] }
          : path.endsWith("/tasks") ? { items: [] }
            : path.endsWith("/approvals") ? { items: [] }
              : path.endsWith("/agents") ? { items: [] }
                : path.endsWith("/documents") ? { documents: [] }
                  : path.endsWith("/leads") ? { items: [] }
                    : path.endsWith("/summary") ? { cards: [], drilldowns: [{ card: "total", dimension: "open", value: 1, recordIds: ["55555555-5555-4555-8555-555555555555"], recordCount: 1, recordsTruncated: false, recordsEndpoint: "/v1/analytics/summary/records" }] }
                      : { events: [] }
      )));
    });
    const service = createWorkspaceService(createAuthenticatedWorkspaceTransport({
      baseUrl: "https://api.example.test",
      getAccessToken: () => Promise.resolve("session-jwt"),
      fetch: fetcher
    }));

    await expect(service.getWorkspaceData()).resolves.toMatchObject({
      currentOrganization: "Tenant A",
      analyticsDrilldowns: [{ card: "total", dimension: "open", value: 1, recordIds: ["55555555-5555-4555-8555-555555555555"], recordCount: 1, recordsTruncated: false, recordsEndpoint: "/v1/analytics/summary/records" }]
    });
    expect(paths).not.toContain("/v1/auth/login");
  });

  it("normalizes the real portal envelope and pending round", () => {
    expect(normalizePortalPreview({
      state: "pending",
      allowedActions: ["approve", "request_changes"],
      item: { title: "Revisao externa", objective: "Validar entrega", round: 3, expiresAt: "2026-07-14T00:00:00Z" }
    })).toMatchObject({ state: "valid", title: "Revisao externa", expectedRound: 3 });
  });

  it("keeps the member workspace available when role-restricted feeds return 403", async () => {
    const restricted = new Set(["/v1/approvals", "/v1/agents", "/v1/experiments", "/v1/analytics/summary", "/v1/audit/events"]);
    const fetcher = vi.fn<typeof fetch>((input) => {
      const path = new URL(input instanceof Request ? input.url : input).pathname;
      if (restricted.has(path)) return Promise.resolve(new Response("{}", { status: 403 }));
      if (path === "/v1/organizations") return Promise.resolve(Response.json({ organizations: [{ id: "tenant-member", name: "Member Tenant" }] }));
      if (path === "/v1/rooms") return Promise.resolve(Response.json({ rooms: [] }));
      if (path === "/v1/tasks") return Promise.resolve(Response.json({ items: [] }));
      if (path === "/v1/knowledge/documents") return Promise.resolve(Response.json({ documents: [] }));
      return Promise.resolve(Response.json({ items: [] }));
    });
    const service = createWorkspaceService(createAuthenticatedWorkspaceTransport({ baseUrl: "https://api.example.test", getAccessToken: () => Promise.resolve("member-jwt"), fetch: fetcher }));
    await expect(service.getWorkspaceData()).resolves.toMatchObject({ currentOrganization: "Member Tenant", governanceMoments: [], automationMoments: [], analyticsMoments: [] });
  });

  it.each([401, 500])("does not mask HTTP %i from a restricted feed", async (status) => {
    const fetcher = vi.fn<typeof fetch>((input) => {
      const path = new URL(input instanceof Request ? input.url : input).pathname;
      if (path === "/v1/approvals") return Promise.resolve(new Response("{}", { status }));
      if (path === "/v1/organizations") return Promise.resolve(Response.json({ organizations: [{ id: "tenant-a", name: "Tenant A" }] }));
      if (path === "/v1/rooms") return Promise.resolve(Response.json({ rooms: [] }));
      if (path === "/v1/tasks") return Promise.resolve(Response.json({ items: [] }));
      if (path === "/v1/knowledge/documents") return Promise.resolve(Response.json({ documents: [] }));
      if (path === "/v1/analytics/summary") return Promise.resolve(Response.json({ cards: [] }));
      if (path === "/v1/audit/events") return Promise.resolve(Response.json({ events: [] }));
      return Promise.resolve(Response.json({ items: [] }));
    });
    const service = createWorkspaceService(createAuthenticatedWorkspaceTransport({ baseUrl: "https://api.example.test", getAccessToken: () => Promise.resolve("jwt"), fetch: fetcher }));
    await expect(service.getWorkspaceData()).rejects.toEqual(expect.objectContaining<Partial<WorkspaceHttpError>>({ status }));
  });
});
