export type RealtimeMessage = {
  id: string;
  clientId?: string;
  body: string;
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
    const duplicate = reconciled.findIndex((candidate) =>
      candidate.id === message.id ||
      Boolean(candidate.clientId && message.clientId && candidate.clientId === message.clientId)
    );
    if (duplicate === -1) reconciled.push(message);
    else reconciled[duplicate] = { ...reconciled[duplicate], ...message };
  }

  return reconciled.sort((left, right) =>
    right.createdAt.localeCompare(left.createdAt) || left.id.localeCompare(right.id)
  );
}
