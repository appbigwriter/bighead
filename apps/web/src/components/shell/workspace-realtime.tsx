"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { connectWorkspaceRealtime } from "@/lib/realtime-refresh";
import {
  createMutationRefreshCoordinator,
  hasActiveWorkspaceMutation,
  MUTATION_END_EVENT,
  MUTATION_START_EVENT
} from "@/lib/mutation-refresh-coordinator";

export function WorkspaceRealtime({ tenantId }: { tenantId: string }) {
  const router = useRouter();

  useEffect(() => {
    let cleanup: () => void = () => undefined;
    const refreshCoordinator = createMutationRefreshCoordinator({
      refresh: () => router.refresh(),
      isBlocked: hasActiveWorkspaceMutation
    });
    const mutationStarted = () => {
      refreshCoordinator.begin();
      disconnect();
    };
    const mutationEnded = (event: Event) => {
      event.preventDefault();
      refreshCoordinator.end(false);
      if (!hasActiveWorkspaceMutation() && navigator.onLine !== false) connect();
    };
    const connect = () => {
      if (hasActiveWorkspaceMutation()) return;
      cleanup();
      const source = new EventSource("/api/realtime");
      cleanup = connectWorkspaceRealtime({
        source,
        refresh: () => refreshCoordinator.request(),
        onReady: () => window.dispatchEvent(new CustomEvent("bighead:realtime-ready")),
        onEvent: (event) => window.dispatchEvent(new CustomEvent("bighead:realtime-event", { detail: event }))
      });
    };
    function disconnect() {
      cleanup();
      cleanup = () => undefined;
    }
    if (!hasActiveWorkspaceMutation()) connect();
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
