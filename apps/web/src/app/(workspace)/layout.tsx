import type { Metadata } from "next";
import type { PropsWithChildren } from "react";
import { redirect } from "next/navigation";

import { WorkspaceShell } from "@/components/shell/workspace-shell";
import { createClient } from "@/lib/supabase/server";
import { shouldUseMockWorkspace } from "@/lib/workspace-mode";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "BigHead" };

export default async function WorkspaceLayout({ children }: PropsWithChildren) {
  if (!shouldUseMockWorkspace()) {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.getClaims();
    if (error || !data?.claims) redirect("/login");
  }
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
