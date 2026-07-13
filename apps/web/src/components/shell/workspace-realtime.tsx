"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { connectWorkspaceRealtime } from "@/lib/realtime-refresh";
import {
  createMutationRefreshCoordinator,
  hasActiveWorkspaceMutation,
  MUTATION_END_EVENT,
  MUTATION_START_EVENT,
  type MutationEndDetail
} from "@/lib/mutation-refresh-coordinator";

export function WorkspaceRealtime({ tenantId }: { tenantId: string }) {
  const router = useRouter();

  useEffect(() => {
    let cleanup: () => void = () => undefined;
    const refreshCoordinator = createMutationRefreshCoordinator({
      refresh: () => router.refresh(),
      isBlocked: hasActiveWorkspaceMutation
    });
    const mutationStarted = () => refreshCoordinator.begin();
    const mutationEnded = (event: Event) => {
      event.preventDefault();
      refreshCoordinator.end((event as CustomEvent<MutationEndDetail>).detail?.refresh === true);
    };
    const connect = () => {
      cleanup();
      const source = new EventSource("/api/realtime");
      cleanup = connectWorkspaceRealtime({
        source,
        refresh: () => refreshCoordinator.request(),
        onReady: () => window.dispatchEvent(new CustomEvent("bighead:realtime-ready")),
        onEvent: (event) => window.dispatchEvent(new CustomEvent("bighead:realtime-event", { detail: event }))
      });
    };
    const disconnect = () => cleanup();
    connect();
    window.addEventListener(MUTATION_START_EVENT, mutationStarted);
    window.addEventListener(MUTATION_END_EVENT, mutationEnded);
    window.addEventListener("offline", disconnect);
    window.addEventListener("online", connect);
    return () => {
      window.removeEventListener("offline", disconnect);
      window.removeEventListener("online", connect);
      window.removeEventListener(MUTATION_START_EVENT, mutationStarted);
      window.removeEventListener(MUTATION_END_EVENT, mutationEnded);
      refreshCoordinator.dispose();
      cleanup();
    };
  }, [router, tenantId]);

  return null;
}
