import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ createClient: vi.fn(), redirect: vi.fn() }));
vi.mock("@/lib/supabase/server", () => ({ createClient: mocks.createClient }));
vi.mock("next/navigation", () => ({ redirect: mocks.redirect }));

import { updatePassword } from "./actions";

describe("updatePassword", () => {
  const getClaims = vi.fn();
  const updateUser = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.redirect.mockImplementation((location: string) => { throw new Error(`REDIRECT:${location}`); });
    mocks.createClient.mockResolvedValue({ auth: { getClaims, updateUser } });
    getClaims.mockResolvedValue({ data: { claims: { sub: "user" } }, error: null });
    updateUser.mockResolvedValue({ error: null });
  });

  it("rejects a weak password before calling Supabase", async () => {
    await expect(updatePassword(form("short"))).rejects.toThrow("weak_password");
    expect(mocks.createClient).not.toHaveBeenCalled();
  });

  it("requires verified recovery claims", async () => {
    getClaims.mockResolvedValueOnce({ data: null, error: null });
    await expect(updatePassword(form("long-enough-password"))).rejects.toThrow("invalid_session");
    expect(updateUser).not.toHaveBeenCalled();
  });

  it("maps provider errors to invalid session", async () => {
    updateUser.mockResolvedValueOnce({ error: new Error("expired") });
    await expect(updatePassword(form("long-enough-password"))).rejects.toThrow("invalid_session");
  });

  it("updates the password for verified claims", async () => {
    await expect(updatePassword(form("long-enough-password"))).rejects.toThrow("password_updated");
    expect(updateUser).toHaveBeenCalledWith({ password: "long-enough-password" });
  });
});

function form(password: string) {
  const data = new FormData();
  data.set("password", password);
  return data;
}
