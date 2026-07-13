import { afterEach, describe, expect, it, vi } from "vitest";

import { connectWorkspaceRealtime } from "./realtime-refresh";

class FakeEventSource {
  onopen: ((event: Event) => void) | null = null;
  close = vi.fn();
  private listeners = new Map<string, EventListener[]>();

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emit(type: string, data: unknown) {
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    this.listeners.get(type)?.forEach((listener) => listener(event));
  }
}

const taskEvent = (id: string, version: number) => ({
  id, table: "tasks", operation: "UPDATE", entityId: "task-1", occurredAt: "2026-07-13T12:00:00Z", version
});

describe("realtime refresh controller", () => {
  afterEach(() => vi.useRealTimers());

  it("debounces bursts, deduplicates ids and ignores stale entity versions", () => {
    vi.useFakeTimers();
    const source = new FakeEventSource();
    const refresh = vi.fn();
    const onReady = vi.fn();
    const onEvent = vi.fn();
    const cleanup = connectWorkspaceRealtime({ source, refresh, onReady, onEvent, debounceMs: 100 });

    source.emit("ready", { retry: 2_000 });
    source.emit("workspace", taskEvent("evt-2", 2));
    source.emit("workspace", taskEvent("evt-2", 2));
    source.emit("workspace", taskEvent("evt-1", 1));
    vi.advanceTimersByTime(100);
    expect(refresh).toHaveBeenCalledTimes(1);
    expect(onReady).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledTimes(1);

    source.emit("workspace", taskEvent("evt-3", 3));
    vi.advanceTimersByTime(100);
    expect(refresh).toHaveBeenCalledTimes(2);
    cleanup();
  });

  it("reconciles after native reconnect and cleanup closes/cancels exactly once", () => {
    vi.useFakeTimers();
    const source = new FakeEventSource();
    const refresh = vi.fn();
    const cleanup = connectWorkspaceRealtime({ source, refresh, debounceMs: 100 });

    source.onopen?.(new Event("open"));
    source.onopen?.(new Event("open"));
    vi.advanceTimersByTime(100);
    expect(refresh).toHaveBeenCalledTimes(1);
    source.onopen?.(new Event("open"));
    cleanup();
    cleanup();
    vi.runAllTimers();
    expect(source.close).toHaveBeenCalledTimes(1);
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});
