import { describe, expect, it } from "vitest";

import { loginFailureLocation } from "./login-failure";

describe("loginFailureLocation", () => {
  it.each([
    new Error("Invalid login credentials"),
    new Error("User not found"),
    new Error("Email not confirmed"),
    { status: 429, message: "rate limited" }
  ])("maps every provider failure to the same non-enumerable response", (providerError) => {
    expect(loginFailureLocation(providerError)).toBe("/login?error=invalid_credentials");
  });
});
