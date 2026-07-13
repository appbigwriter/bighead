import { describe, expect, it } from "vitest";

import { getWorkspaceRequestContext } from "./workspace-request-context";

describe("SSR workspace request context", () => {
  it("keeps concurrent tenant requests and abort signals isolated", async () => {
    const controllerA = new AbortController();
    const controllerB = new AbortController();
    let releaseA!: () => void;
    const gateA = new Promise<void>((resolve) => { releaseA = resolve; });

    const requestA = getWorkspaceRequestContext(controllerA.signal, async () => {
      await gateA;
      return { get: () => ({ value: "tenant-a" }) };
    });
    const requestB = getWorkspaceRequestContext(controllerB.signal, () =>
      Promise.resolve({ get: () => ({ value: "tenant-b" }) })
    );

    const contextB = await requestB;
    releaseA();
    const contextA = await requestA;

    expect(contextA).toEqual({ tenantId: "tenant-a", signal: controllerA.signal });
    expect(contextB).toEqual({ tenantId: "tenant-b", signal: controllerB.signal });
    expect(contextA.signal).not.toBe(contextB.signal);
    expect(Object.isFrozen(contextA)).toBe(true);
  });

  it("omits an absent or blank tenant cookie", async () => {
    await expect(getWorkspaceRequestContext(undefined, () => Promise.resolve({ get: () => ({ value: "  " }) })))
      .resolves.toEqual({});
  });
});
