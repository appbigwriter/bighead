import { cookies } from "next/headers";

import type { WorkspaceRequestContext } from "./workspace-service";

type CookieReader = () => Promise<{ get(name: string): { value: string } | undefined }>;

/** Creates an immutable context for one SSR request; no tenant state is shared. */
export async function getWorkspaceRequestContext(
  signal?: AbortSignal,
  readCookies: CookieReader = cookies
): Promise<WorkspaceRequestContext> {
  const cookieStore = await readCookies();
  const tenantId = cookieStore.get("bighead-organization-id")?.value.trim();

  return Object.freeze({
    ...(tenantId ? { tenantId } : {}),
    ...(signal ? { signal } : {})
  });
}
