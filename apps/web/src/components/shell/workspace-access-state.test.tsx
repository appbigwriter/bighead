import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WorkspaceHttpError, WorkspaceMembershipError } from "@/lib/workspace-service";
import { classifyWorkspaceAccessError, WorkspaceAccessState } from "./workspace-access-state";

describe("workspace access states", () => {
  it("classifies empty membership and sends the user to onboarding", () => {
    expect(classifyWorkspaceAccessError(new WorkspaceMembershipError())).toBe("tenant-empty");
    render(<WorkspaceAccessState kind="tenant-empty" />);
    expect(screen.getByRole("link", { name: "Iniciar onboarding" })).toHaveAttribute("href", "/acesso/onboarding");
  });

  it("classifies permission denial without masking other failures", () => {
    expect(classifyWorkspaceAccessError(new WorkspaceHttpError(403, "/v1/tasks"))).toBe("permission-denied");
    expect(classifyWorkspaceAccessError(new WorkspaceHttpError(500, "/v1/tasks"))).toBeNull();
    render(<WorkspaceAccessState kind="permission-denied" />);
    expect(screen.getByRole("link", { name: "Voltar ao inicio" })).toHaveAttribute("href", "/operacao/home");
  });
});
