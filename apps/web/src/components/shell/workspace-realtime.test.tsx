import { act, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type * as NextNavigation from "next/navigation";

const { refresh } = vi.hoisted(() => ({ refresh: vi.fn() }));

vi.mock("next/navigation", async () => ({
  ...(await vi.importActual<typeof NextNavigation>("next/navigation")),
  useRouter: () => ({ refresh })
}));

import { beginWorkspaceMutation, endWorkspaceMutation } from "@/lib/mutation-refresh-coordinator";
import { WorkspaceRealtime } from "./workspace-realtime";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static lifecycle: string[] = [];
  onopen: ((event: Event) => void) | null = null;
  close = vi.fn(() => FakeEventSource.lifecycle.push(`close:${this.url}`));
  private listeners = new Map<string, EventListener[]>();

  constructor(public readonly url: string) {
    FakeEventSource.instances.push(this);
    FakeEventSource.lifecycle.push(`open:${url}`);
  }

  addEventListener(type: string, listener: EventListener) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  emit(type: string, data: unknown) {
    const event = new MessageEvent(type, { data: JSON.stringify(data) });
    this.listeners.get(type)?.forEach((listener) => listener(event));
  }
}

describe("WorkspaceRealtime tenant lifecycle", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    FakeEventSource.lifecycle = [];
    refresh.mockReset();
    vi.stubGlobal("EventSource", FakeEventSource);
  });

  afterEach(() => vi.useRealTimers());

  it("closes the old stream before binding the selected tenant context", async () => {
    const view = render(<WorkspaceRealtime tenantId="tenant-a" />);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const first = FakeEventSource.instances[0]!;

    view.rerender(<WorkspaceRealtime tenantId="tenant-b" />);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(2));
    expect(first.close).toHaveBeenCalledTimes(1);
    expect(FakeEventSource.lifecycle).toEqual(["open:/api/realtime", "close:/api/realtime", "open:/api/realtime"]);
    view.unmount();
    expect(FakeEventSource.instances[1]!.close).toHaveBeenCalledTimes(1);
  });

  it("replaces the stream on browser online without remounting workspace state", async () => {
    const view = render(<WorkspaceRealtime tenantId="tenant-a" />);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const first = FakeEventSource.instances[0]!;
    window.dispatchEvent(new Event("online"));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(2));
    expect(first.close).toHaveBeenCalledTimes(1);
    view.unmount();
  });

  it("closes while offline before establishing a fresh online stream", async () => {
    const view = render(<WorkspaceRealtime tenantId="tenant-a" />);
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1));
    const first = FakeEventSource.instances[0]!;
    window.dispatchEvent(new Event("offline"));
    expect(first.close).toHaveBeenCalledTimes(1);
    window.dispatchEvent(new Event("online"));
    await waitFor(() => expect(FakeEventSource.instances).toHaveLength(2));
    view.unmount();
  });

  it("keeps refresh blocked when the realtime component remounts during a mutation", () => {
    vi.useFakeTimers();
    const view = render(<WorkspaceRealtime tenantId="tenant-a" />);
    beginWorkspaceMutation();
    expect(FakeEventSource.instances[0]!.close).toHaveBeenCalledTimes(1);
    expect(refresh).not.toHaveBeenCalled();

    view.rerender(<WorkspaceRealtime tenantId="tenant-b" />);
    expect(FakeEventSource.instances).toHaveLength(1);
    expect(refresh).not.toHaveBeenCalled();

    act(() => {
      endWorkspaceMutation(true);
    });
    expect(FakeEventSource.instances).toHaveLength(2);
    act(() => {
      FakeEventSource.instances[1]!.emit("ready", { retry: 2_000 });
      vi.runAllTimers();
    });
    expect(refresh).toHaveBeenCalledTimes(1);
    view.unmount();
  });

  it("reconnects once only after the last nested mutation ends", () => {
    const view = render(<WorkspaceRealtime tenantId="tenant-a" />);
    beginWorkspaceMutation();
    beginWorkspaceMutation();
    expect(FakeEventSource.instances[0]!.close).toHaveBeenCalledTimes(1);

    endWorkspaceMutation(false);
    expect(FakeEventSource.instances).toHaveLength(1);
    endWorkspaceMutation(true);
    expect(FakeEventSource.instances).toHaveLength(2);
    view.unmount();
  });

  it("does not reconnect on online until the active mutation ends", () => {
    const view = render(<WorkspaceRealtime tenantId="tenant-a" />);
    beginWorkspaceMutation();
    window.dispatchEvent(new Event("offline"));
    window.dispatchEvent(new Event("online"));
    expect(FakeEventSource.instances).toHaveLength(1);

    endWorkspaceMutation(false);
    expect(FakeEventSource.instances).toHaveLength(2);
    view.unmount();
  });
});
