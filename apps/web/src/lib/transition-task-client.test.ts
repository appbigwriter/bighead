import { afterEach, describe, expect, it, vi } from "vitest";

import { transitionTask } from "./transition-task-client";

function transitionForm() {
  const form = new FormData();
  form.set("organizationId", "attacker-controlled-tenant");
  form.set("taskId", "7724feab-c777-4b59-9d70-7598d40662ba");
  form.set("targetState", "triaged");
  form.set("expectedVersion", "1");
  form.set("reason", "Validacao client");
  return form;
}

describe("transition task browser client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("uses the same-origin BFF without forwarding the form tenant", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      ok: true,
      status: 200,
      message: "Tarefa movida para triaged.",
      data: { taskId: "7724feab-c777-4b59-9d70-7598d40662ba", version: 2, status: "triaged" }
    }), { status: 200, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await transitionTask(transitionForm());

    expect(result.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/tasks/7724feab-c777-4b59-9d70-7598d40662ba/transition",
      expect.objectContaining({ method: "POST", cache: "no-store" })
    );
    const [, options] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    const body = JSON.parse(options.body as string) as Record<string, unknown>;
    expect(body).toEqual({ targetState: "triaged", expectedVersion: 1, reason: "Validacao client" });
    expect(body).not.toHaveProperty("organizationId");
  });

  it("normalizes a network failure without retrying the non-idempotent transition", async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError("network down"));
    vi.stubGlobal("fetch", fetchMock);
    await expect(transitionTask(transitionForm())).resolves.toEqual({
      ok: false,
      status: 503,
      message: "Servico indisponivel. Tente novamente sem repetir a operacao."
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
