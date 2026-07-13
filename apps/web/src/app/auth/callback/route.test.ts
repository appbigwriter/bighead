import { beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({ createClient: vi.fn() }));
vi.mock("@/lib/supabase/server", () => ({ createClient: mocks.createClient }));

import { GET } from "./route";

describe("GET /auth/callback", () => {
  const exchangeCodeForSession = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubEnv("APP_URL", "https://app.bighead.example");
    mocks.createClient.mockResolvedValue({ auth: { exchangeCodeForSession } });
    exchangeCodeForSession.mockResolvedValue({ error: null });
  });

  it("rejects a callback without a PKCE code", async () => {
    const response = await GET(new NextRequest("https://app.bighead.example/auth/callback"));
    expect(response.headers.get("location")).toBe("https://app.bighead.example/login?error=invalid_callback");
    expect(mocks.createClient).not.toHaveBeenCalled();
  });

  it("maps provider exchange errors to a non-sensitive failure", async () => {
    exchangeCodeForSession.mockResolvedValueOnce({ error: new Error("provider detail") });
    const response = await GET(new NextRequest("https://app.bighead.example/auth/callback?code=bad"));
    expect(exchangeCodeForSession).toHaveBeenCalledWith("bad");
    expect(response.headers.get("location")).toBe("https://app.bighead.example/login?error=invalid_callback");
  });

  it("exchanges the code and redirects to the internal destination", async () => {
    const response = await GET(new NextRequest("https://app.bighead.example/auth/callback?code=valid&next=%2Fauth%2Fupdate-password"));
    expect(response.headers.get("location")).toBe("https://app.bighead.example/auth/update-password");
  });

  it("falls back when next targets another host", async () => {
    const response = await GET(new NextRequest("https://app.bighead.example/auth/callback?code=valid&next=https%3A%2F%2Fevil.example"));
    expect(response.headers.get("location")).toBe("https://app.bighead.example/operacao/home");
  });
});
