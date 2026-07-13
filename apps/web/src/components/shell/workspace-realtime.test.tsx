import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type * as NextNavigation from "next/navigation";

vi.mock("next/navigation", async () => ({
  ...(await vi.importActual<typeof NextNavigation>("next/navigation")),
  useRouter: () => ({ refresh: vi.fn() })
}));

import { WorkspaceRealtime } from "./workspace-realtime";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static lifecycle: string[] = [];
  onopen: ((event: Event) => void) | null = null;
  close = vi.fn(() => FakeEventSource.lifecycle.push(`close:${this.url}`));

  constructor(public readonly url: string) {
    FakeEventSource.instances.push(this);
    FakeEventSource.lifecycle.push(`open:${url}`);
  }

  addEventListener() { /* messages are covered by realtime-refresh tests */ }
}

describe("WorkspaceRealtime tenant lifecycle", () => {
  beforeEach(() => {
    FakeEventSource.instances = [];
    FakeEventSource.lifecycle = [];
    vi.stubGlobal("EventSource", FakeEventSource);
  });

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
});
