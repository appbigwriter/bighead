import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedApi, revalidatePath } = vi.hoisted(() => ({
  authenticatedApi: vi.fn(),
  revalidatePath: vi.fn()
}));

vi.mock("@/lib/server-api-client", () => ({ authenticatedApi, publicApi: vi.fn() }));
vi.mock("@/lib/workspace-mode", () => ({ shouldUseMockWorkspace: () => false }));
vi.mock("next/cache", () => ({ revalidatePath }));
vi.mock("next/headers", () => ({ cookies: vi.fn() }));

import { transitionTask } from "./critical-mutations";

describe("transitionTask", () => {
  beforeEach(() => {
    authenticatedApi.mockReset();
    revalidatePath.mockReset();
  });

  it("returns the committed transition before client-driven revalidation", async () => {
    authenticatedApi.mockResolvedValue({
      task: { id: "task-1", version: 2, status: "triaged" }
    });
    const form = new FormData();
    form.set("organizationId", "org-1");
    form.set("taskId", "task-1");
    form.set("targetState", "triaged");
    form.set("expectedVersion", "1");
    form.set("reason", "Validacao E2E");

    const result = await transitionTask(form);

    expect(result).toEqual({
      ok: true,
      status: 200,
      message: "Tarefa movida para triaged.",
      data: { taskId: "task-1", version: 2, status: "triaged" }
    });
    expect(revalidatePath).not.toHaveBeenCalled();
  });
});
