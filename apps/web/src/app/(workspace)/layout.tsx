import type { PropsWithChildren } from "react";

import { WorkspaceShell } from "@/components/shell/workspace-shell";

export default function WorkspaceLayout({ children }: PropsWithChildren) {
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
