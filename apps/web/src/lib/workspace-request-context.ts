import { headers } from "next/headers";

import type { WorkspaceRequestContext } from "./workspace-service";

type HeaderReader = () => Promise<Pick<Headers, "get">>;

/** Creates an immutable context for one SSR request; no tenant state is shared. */
export async function getWorkspaceRequestContext(
  signal?: AbortSignal,
  readHeaders: HeaderReader = headers
): Promise<WorkspaceRequestContext> {
  const requestHeaders = await readHeaders();
  const tenantId = requestHeaders.get("x-tenant-id")?.trim();

  return Object.freeze({
    ...(tenantId ? { tenantId } : {}),
    ...(signal ? { signal } : {})
  });
}
