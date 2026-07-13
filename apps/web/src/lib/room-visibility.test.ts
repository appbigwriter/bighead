import { describe, expect, it } from "vitest";

import { visibleRoomsForMember } from "./room-visibility";

describe("visibleRoomsForMember", () => {
  it("removes inaccessible private rooms from results and every counter", () => {
    const result = visibleRoomsForMember([
      { id: "public", name: "Publica", unreadCount: 2 },
      { id: "private-ok", name: "Privada autorizada", isPrivate: true, hasAccess: true, unreadCount: 3 },
      { id: "private-denied", name: "Privada proibida", isPrivate: true, hasAccess: false, unreadCount: 99 }
    ]);
    expect(result.items.map((room) => room.id)).toEqual(["public", "private-ok"]);
    expect(result.counters).toEqual({ total: 2, unread: 5, private: 1 });
    expect(JSON.stringify(result)).not.toContain("private-denied");
  });
});
