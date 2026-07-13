export type RoomVisibility = {
  id: string;
  name: string;
  isPrivate?: boolean;
  hasAccess?: boolean;
  unreadCount?: number;
};

export function visibleRoomsForMember<T extends RoomVisibility>(rooms: T[]) {
  const items = rooms.filter((room) => !room.isPrivate || room.hasAccess !== false);
  return {
    items,
    counters: {
      total: items.length,
      unread: items.reduce((sum, room) => sum + (room.unreadCount ?? 0), 0),
      private: items.filter((room) => room.isPrivate).length
    }
  };
}
