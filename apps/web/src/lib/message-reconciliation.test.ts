import { describe, expect, it } from "vitest";

import { reconcileRealtimeMessages, type RealtimeMessage } from "./message-reconciliation";

const message = (id: string, clientId: string, body = id): RealtimeMessage => ({
  id,
  clientId,
  body,
  createdAt: "2026-07-13T12:00:00Z"
});

describe("realtime message reconciliation", () => {
  it("replaces an optimistic id with the persisted message by client id", () => {
    expect(reconcileRealtimeMessages(
      [message("temp-1", "client-1", "enviando")],
      [message("message-1", "client-1", "persistida")]
    )).toEqual([message("message-1", "client-1", "persistida")]);
  });

  it("does not duplicate the same message after reconnect snapshots or repeated events", () => {
    const persisted = message("message-1", "client-1");
    expect(reconcileRealtimeMessages([persisted], [persisted, persisted])).toEqual([persisted]);
  });
});
