import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  cookies: vi.fn(),
  getValidatedAccessToken: vi.fn(),
  redirect: vi.fn()
}));

vi.mock("next/headers", () => ({ cookies: mocks.cookies }));
vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));
vi.mock("@/lib/server-api-client", () => ({
  getValidatedAccessToken: mocks.getValidatedAccessToken
}));

import { submitOnboarding } from "./actions";

describe("submitOnboarding", () => {
  const cookieStore = { set: vi.fn() };

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.cookies.mockResolvedValue(cookieStore);
    mocks.getValidatedAccessToken.mockResolvedValue("access-token");
    mocks.redirect.mockImplementation((location: string) => {
      throw new Error(`REDIRECT:${location}`);
    });
    vi.stubEnv("API_URL", "http://api.bighead.test");
  });

  it("persists the canonical camelCase organization id before a relative redirect", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({
      organizationId: "org-created",
      nextRoute: "/operacao/home"
    }), { status: 200, headers: { "content-type": "application/json" } }));

    await expect(submitOnboarding(onboardingForm())).rejects.toThrow("REDIRECT:/operacao/home");

    expect(cookieStore.set).toHaveBeenCalledWith(
      "bighead-organization-id",
      "org-created",
      expect.objectContaining({ httpOnly: true, sameSite: "lax", path: "/" })
    );
  });
});

function onboardingForm() {
  const data = new FormData();
  data.set("displayName", "Owner E2E");
  data.set("organizationName", "Onboarding E2E");
  data.set("organizationSlug", "onboarding-e2e");
  return data;
}
