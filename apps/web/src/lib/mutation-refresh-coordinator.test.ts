import { afterEach, describe, expect, it, vi } from "vitest";

import { createMutationRefreshCoordinator } from "./mutation-refresh-coordinator";

describe("mutation refresh coordinator", () => {
  afterEach(() => vi.useRealTimers());

  it("holds realtime refresh until the active mutation has delivered its result", () => {
    vi.useFakeTimers();
    const refresh = vi.fn();
    const coordinator = createMutationRefreshCoordinator({ refresh });

    coordinator.begin();
    coordinator.request();
    vi.runAllTimers();
    expect(refresh).not.toHaveBeenCalled();

    coordinator.end(true);
    vi.runAllTimers();
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("coalesces nested mutations and realtime events into one deferred refresh", () => {
    vi.useFakeTimers();
    const refresh = vi.fn();
    const coordinator = createMutationRefreshCoordinator({ refresh });

    coordinator.begin();
    coordinator.begin();
    coordinator.request();
    coordinator.end(true);
    vi.runAllTimers();
    expect(refresh).not.toHaveBeenCalled();

    coordinator.end(true);
    vi.runAllTimers();
    expect(refresh).toHaveBeenCalledTimes(1);
  });

  it("rechecks the mutation gate when an already scheduled refresh fires", () => {
    vi.useFakeTimers();
    const refresh = vi.fn();
    const coordinator = createMutationRefreshCoordinator({ refresh });

    coordinator.request();
    coordinator.begin();
    vi.runAllTimers();
    expect(refresh).not.toHaveBeenCalled();

    coordinator.end();
    vi.runAllTimers();
    expect(refresh).toHaveBeenCalledTimes(1);
  });
});
