import { describe, expect, it } from "vitest";

import { shouldUseMockWorkspace } from "./workspace-mode";

describe("workspace runtime policy", () => {
  it("fails closed when mock mode is requested in production", () => {
    expect(() => shouldUseMockWorkspace({
      BIGHEAD_WORKSPACE_MODE: "mock",
      NODE_ENV: "production"
    })).toThrow("forbidden in production");
  });

  it("allows fixtures only in a non-production harness", () => {
    expect(shouldUseMockWorkspace({ BIGHEAD_WORKSPACE_MODE: "mock", NODE_ENV: "development" })).toBe(true);
    expect(shouldUseMockWorkspace({ BIGHEAD_WORKSPACE_MODE: "real", NODE_ENV: "production" })).toBe(false);
  });
});
