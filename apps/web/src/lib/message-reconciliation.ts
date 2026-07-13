export type RealtimeMessage = {
  id: string;
  roomId: string;
  clientId?: string;
  authorUserId?: string;
  body: string;
  metadata?: Record<string, unknown>;
  editedAt?: string;
  deletedAt?: string;
  pending?: boolean;
  createdAt: string;
};

/**
 * Reconciles the authoritative HTTP snapshot with the currently rendered
 * timeline. Reconnects and optimistic retries may present the same message by
 * database id, client id, or both; none of those paths may create a second row.
 */
export function reconcileRealtimeMessages(
  current: RealtimeMessage[],
  incoming: RealtimeMessage[]
): RealtimeMessage[] {
  const reconciled: RealtimeMessage[] = [];

  for (const message of [...current, ...incoming]) {
    const duplicates = reconciled.flatMap((candidate, index) => (
      candidate.id === message.id ||
      Boolean(candidate.clientId && message.clientId && candidate.clientId === message.clientId)
    ) ? [index] : []);
    if (duplicates.length === 0) {
      reconciled.push(message);
      continue;
    }
    const merged = duplicates.reduce((result, index) => ({ ...result, ...reconciled[index] }), message);
    for (const index of duplicates.reverse()) reconciled.splice(index, 1);
    reconciled.push({ ...merged, ...message });
  }

  return reconciled.sort((left, right) =>
    right.createdAt.localeCompare(left.createdAt) || left.id.localeCompare(right.id)
  );
}
