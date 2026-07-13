import { parseWorkspaceRealtimeEvent, type WorkspaceRealtimeEvent } from "./realtime-protocol";

type EventSourcePort = {
  onopen: ((event: Event) => void) | null;
  addEventListener(type: string, listener: EventListener): void;
  close(): void;
};

type Timer = ReturnType<typeof setTimeout>;

export function connectWorkspaceRealtime(options: {
  source: EventSourcePort;
  refresh: () => void;
  onReady?: () => void;
  onEvent?: (event: WorkspaceRealtimeEvent) => void;
  debounceMs?: number;
  maxSeen?: number;
  setTimer?: (callback: () => void, delay: number) => Timer;
  clearTimer?: (timer: Timer) => void;
}) {
  const { source, refresh, onReady, onEvent, debounceMs = 250, maxSeen = 256, setTimer = setTimeout, clearTimer = clearTimeout } = options;
  const seen = new Map<string, true>();
  const versions = new Map<string, number>();
  let timer: Timer | undefined;
  let closed = false;

  const schedule = () => {
    if (closed || timer) return;
    timer = setTimer(() => {
      timer = undefined;
      if (!closed) refresh();
    }, debounceMs);
  };

  const accept = (event: WorkspaceRealtimeEvent) => {
    if (seen.has(event.id)) return false;
    const entityKey = `${event.table}:${event.entityId}`;
    const lastVersion = versions.get(entityKey);
    if (event.version !== undefined && lastVersion !== undefined && event.version <= lastVersion) return false;
    seen.set(event.id, true);
    if (event.version !== undefined) versions.set(entityKey, event.version);
    while (seen.size > maxSeen) seen.delete(seen.keys().next().value as string);
    return true;
  };

  source.onopen = schedule; // EventSource invokes this again after its native reconnect.
  source.addEventListener("ready", () => {
    onReady?.();
    schedule();
  });
  source.addEventListener("workspace", ((message: MessageEvent<string>) => {
    try {
      const event = parseWorkspaceRealtimeEvent(JSON.parse(message.data));
      if (event && accept(event)) {
        onEvent?.(event);
        schedule();
      }
    } catch {
      // Malformed server events never mutate UI state.
    }
  }) as EventListener);

  return () => {
    if (closed) return;
    closed = true;
    if (timer) clearTimer(timer);
    source.close();
  };
}
