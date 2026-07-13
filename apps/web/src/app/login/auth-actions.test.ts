import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ createClient: vi.fn(), redirect: vi.fn() }));
vi.mock("@/lib/supabase/server", () => ({ createClient: mocks.createClient }));
vi.mock("@/lib/supabase/auth-config", () => ({ readSupabaseAuthRuntimeConfig: () => ({ appUrl: "https://app.bighead.example" }) }));
vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));
vi.mock("next/headers", () => ({ cookies: vi.fn() }));

import { requestMagicLink, requestPasswordReset } from "./actions";

describe("passwordless Auth actions", () => {
  const signInWithOtp = vi.fn();
  const resetPasswordForEmail = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.redirect.mockImplementation((location: string) => { throw new Error(`REDIRECT:${location}`); });
    mocks.createClient.mockResolvedValue({ auth: { signInWithOtp, resetPasswordForEmail } });
    signInWithOtp.mockResolvedValue({ error: null });
    resetPasswordForEmail.mockResolvedValue({ error: null });
  });

  it("uses the canonical PKCE callback for magic links", async () => {
    await expect(requestMagicLink(form("person@example.com"))).rejects.toThrow("REDIRECT:/login?status=email_sent");
    expect(signInWithOtp).toHaveBeenCalledWith({ email: "person@example.com", options: { emailRedirectTo: "https://app.bighead.example/auth/callback" } });
  });

  it("uses the canonical update-password callback for recovery", async () => {
    await expect(requestPasswordReset(form("person@example.com"))).rejects.toThrow("REDIRECT:/login?status=email_sent");
    expect(resetPasswordForEmail).toHaveBeenCalledWith("person@example.com", { redirectTo: "https://app.bighead.example/auth/callback?next=/auth/update-password" });
  });

  it.each(["magic", "reset"])("does not enumerate accounts when %s provider call fails", async (flow) => {
    signInWithOtp.mockResolvedValueOnce({ error: new Error("unknown account") });
    resetPasswordForEmail.mockResolvedValueOnce({ error: new Error("unknown account") });
    const action = flow === "magic" ? requestMagicLink : requestPasswordReset;
    await expect(action(form("missing@example.com"))).rejects.toThrow("REDIRECT:/login?status=email_sent");
  });
});

function form(email: string) {
  const data = new FormData();
  data.set("email", email);
  return data;
}
