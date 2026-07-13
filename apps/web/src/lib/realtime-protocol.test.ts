import { describe, expect, it } from "vitest";

import { encodeSse, isSameSiteEventSource, isUuid, parseWorkspaceRealtimeEvent } from "./realtime-protocol";

describe("realtime protocol boundary", () => {
  it("accepts only UUID tenant identifiers and same-site requests", () => {
    expect(isUuid("018f5f20-3b1a-4ae6-8d3f-5bd5a64f2527")).toBe(true);
    expect(isUuid("a7100000-0000-0000-0000-000000000001")).toBe(true);
    expect(isUuid("tenant-a,organization_id=neq.x")).toBe(false);
    expect(isSameSiteEventSource("https://app.bighead.test/api/realtime", "same-origin", "https://app.bighead.test")).toBe(true);
    expect(isSameSiteEventSource("https://app.bighead.test/api/realtime", "cross-site", "https://evil.test")).toBe(false);
  });

  it("parses the allowlisted event envelope and emits valid SSE", () => {
    const event = { id: "evt-1", table: "tasks", operation: "UPDATE", entityId: "task-1", occurredAt: "2026-07-13T12:00:00Z", version: 2 };
    expect(parseWorkspaceRealtimeEvent(event)).toEqual(event);
    expect(parseWorkspaceRealtimeEvent({ ...event, table: "organization_members" })).toBeNull();
    expect(encodeSse("workspace", event, event.id)).toContain("event: workspace\ndata:");
  });
});
