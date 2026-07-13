"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { connectWorkspaceRealtime } from "@/lib/realtime-refresh";

export function WorkspaceRealtime({ tenantId }: { tenantId: string }) {
  const router = useRouter();

  useEffect(() => {
    const source = new EventSource("/api/realtime");
    return connectWorkspaceRealtime({ source, refresh: () => router.refresh() });
  }, [router, tenantId]);

  return null;
}
