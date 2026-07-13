import "server-only";
import { redirect } from "next/navigation";

import { createClient } from "./supabase/server";
import {
  createAuthenticatedWorkspaceTransport,
  createHttpWorkspaceTransport,
  createMockWorkspaceTransport,
  createWorkspaceService,
  type WorkspaceRequestContext
} from "./workspace-service";
import { shouldUseMockWorkspace } from "./workspace-mode";

function apiBaseUrl() {
  const value = process.env.API_URL?.trim() || process.env.NEXT_PUBLIC_API_URL?.trim();
  if (!value) throw new Error("API_URL is required for the production workspace");
  return value;
}

export async function getServerWorkspaceData(context?: WorkspaceRequestContext) {
  if (shouldUseMockWorkspace()) {
    return createWorkspaceService(createMockWorkspaceTransport()).getWorkspaceData(context);
  }

  const supabase = await createClient();
  const { data: claims, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claims?.claims) redirect("/login");
  const { data, error } = await supabase.auth.getSession();
  const accessToken = data.session?.access_token;
  if (error || !accessToken) redirect("/login");

  return createWorkspaceService(createAuthenticatedWorkspaceTransport({
    baseUrl: apiBaseUrl(),
    getAccessToken: () => Promise.resolve(accessToken)
  })).getWorkspaceData(context);
}

export async function getPublicPortalPreview(token: string, context?: WorkspaceRequestContext) {
  if (shouldUseMockWorkspace()) {
    return createWorkspaceService(createMockWorkspaceTransport()).getPortalPreview(token, context);
  }
  const preview = await createWorkspaceService(createHttpWorkspaceTransport({
    baseUrl: `${apiBaseUrl().replace(/\/$/, "")}/v1`
  })).getPortalPreview(token, context);
  return { ...preview, token };
}
