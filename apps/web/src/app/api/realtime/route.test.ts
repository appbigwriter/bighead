import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  createClient: vi.fn(),
  getContext: vi.fn(),
  mockMode: vi.fn(() => false)
}));

vi.mock("@/lib/supabase/server", () => ({ createClient: mocks.createClient }));
vi.mock("@/lib/workspace-request-context", () => ({ getWorkspaceRequestContext: mocks.getContext }));
vi.mock("@/lib/workspace-mode", () => ({ shouldUseMockWorkspace: mocks.mockMode }));

import { GET } from "./route";

const tenantId = "018f5f20-3b1a-4ae6-8d3f-5bd5a64f2527";

function fakeSupabase(options: { claims?: boolean; session?: boolean; membership?: boolean } = {}) {
  const channel = {
    on: vi.fn().mockReturnThis(),
    subscribe: vi.fn((callback: (status: string) => void) => { callback("SUBSCRIBED"); return channel; })
  };
  const removeChannel = vi.fn().mockResolvedValue("ok");
  return {
    auth: {
      getClaims: vi.fn().mockResolvedValue(options.claims === false ? { data: null, error: new Error("bad") } : { data: { claims: { sub: "user" } }, error: null }),
      getSession: vi.fn().mockResolvedValue(options.session === false ? { data: { session: null }, error: null } : { data: { session: { access_token: "server-secret-token", expires_at: Math.floor(Date.now() / 1000) + 3600 } }, error: null })
    },
    from: vi.fn(() => ({ select: vi.fn().mockReturnThis(), eq: vi.fn().mockReturnThis(), maybeSingle: vi.fn().mockResolvedValue(options.membership === false ? { data: null, error: null } : { data: { id: tenantId }, error: null }) })),
    realtime: { setAuth: vi.fn().mockResolvedValue(undefined) },
    channel: vi.fn(() => channel),
    removeChannel
  };
}

describe("GET /api/realtime", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.mockMode.mockReturnValue(false);
    mocks.getContext.mockResolvedValue({ tenantId });
  });

  it("rejects missing/tampered tenant context before opening a channel", async () => {
    mocks.getContext.mockResolvedValueOnce({ tenantId: "tenant-a,organization_id=neq.x" });
    const response = await GET(new Request("https://app.bighead.test/api/realtime"));
    expect(response.status).toBe(400);
    expect(mocks.createClient).not.toHaveBeenCalled();
  });

  it("rejects invalid sessions and inactive tenant membership", async () => {
    mocks.createClient.mockResolvedValueOnce(fakeSupabase({ claims: false }));
    expect((await GET(new Request("https://app.bighead.test/api/realtime"))).status).toBe(401);
    mocks.createClient.mockResolvedValueOnce(fakeSupabase({ membership: false }));
    expect((await GET(new Request("https://app.bighead.test/api/realtime"))).status).toBe(403);
  });

  it("opens a non-buffered stream and removes its channel on abort without exposing the token", async () => {
    const supabase = fakeSupabase();
    mocks.createClient.mockResolvedValue(supabase);
    const abort = new AbortController();
    const request = { url: "https://app.bighead.test/api/realtime", headers: new Headers(), signal: abort.signal } as Request;
    const response = await GET(request);
    expect(response.status).toBe(200);
    expect(response.headers.get("content-type")).toContain("text/event-stream");
    expect(response.headers.get("cache-control")).toBe("no-cache, no-transform");
    const first = await response.body?.getReader().read();
    expect(new TextDecoder().decode(first?.value)).not.toContain("server-secret-token");
    abort.abort();
    await vi.waitFor(() => expect(supabase.removeChannel).toHaveBeenCalledTimes(1));
  });
});
