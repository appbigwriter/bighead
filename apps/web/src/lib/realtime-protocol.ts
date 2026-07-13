export type WorkspaceRealtimeEvent = {
  id: string;
  table: "messages" | "tasks" | "notifications";
  operation: "INSERT" | "UPDATE";
  entityId: string;
  occurredAt: string;
  version?: number;
};

// PostgreSQL accepts all UUID bit patterns; constrain syntax to prevent filter injection.
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const TABLES = new Set(["messages", "tasks", "notifications"]);
const OPERATIONS = new Set(["INSERT", "UPDATE"]);

export function isUuid(value: string | undefined): value is string {
  return Boolean(value && UUID.test(value));
}

export function parseWorkspaceRealtimeEvent(value: unknown): WorkspaceRealtimeEvent | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  if (typeof item.id !== "string" || !TABLES.has(String(item.table)) || !OPERATIONS.has(String(item.operation))) return null;
  if (typeof item.entityId !== "string" || typeof item.occurredAt !== "string" || Number.isNaN(Date.parse(item.occurredAt))) return null;
  if (item.version !== undefined && (!Number.isInteger(item.version) || Number(item.version) < 0)) return null;
  return item as WorkspaceRealtimeEvent;
}

export function encodeSse(event: string, data: unknown, id?: string) {
  return `${id ? `id: ${id}\n` : ""}event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export function isSameSiteEventSource(requestUrl: string, secFetchSite: string | null, origin: string | null) {
  if (secFetchSite === "cross-site") return false;
  if (!origin) return true;
  return new URL(origin).origin === new URL(requestUrl).origin;
}
