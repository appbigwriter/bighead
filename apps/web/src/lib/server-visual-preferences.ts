import "server-only";

import { authenticatedApi } from "./server-api-client";
import { DEFAULT_VISUAL_PREFERENCES, type VisualPreferences } from "./theme-preference";
import { getWorkspaceRequestContext } from "./workspace-request-context";

export async function getServerVisualPreferences(): Promise<VisualPreferences> {
  try {
    const organizationId = (await getWorkspaceRequestContext()).tenantId;
    if (!organizationId) return DEFAULT_VISUAL_PREFERENCES;
    const response = await authenticatedApi<{ preferences?: { theme?: unknown; accessibility?: unknown } }>("/v1/preferences", { organizationId });
    const accessibility = response.preferences?.accessibility;
    const a11y = accessibility && typeof accessibility === "object" && !Array.isArray(accessibility) ? accessibility as Record<string, unknown> : {};
    return {
      theme: response.preferences?.theme === "dark" ? "radar-dark" : "aurora-light",
      density: a11y.density === "compact" ? "compact" : "comfortable",
      motion: a11y.reducedMotion === true ? "reduced" : "full"
    };
  } catch {
    return DEFAULT_VISUAL_PREFERENCES;
  }
}
