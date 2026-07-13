type RuntimeEnvironment = {
  BIGHEAD_WORKSPACE_MODE?: string;
  NODE_ENV?: string;
};

export function shouldUseMockWorkspace(environment: RuntimeEnvironment = process.env) {
  if (environment.BIGHEAD_WORKSPACE_MODE !== "mock") return false;
  if (environment.NODE_ENV === "production") {
    throw new Error("Mock workspace mode is forbidden in production");
  }
  return true;
}
