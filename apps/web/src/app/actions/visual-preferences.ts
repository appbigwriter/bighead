"use server";

import { authenticatedApi } from "@/lib/server-api-client";

export async function saveVisualPreferences(input: { organizationId: string; theme: string; density: string; motion: string }) {
  await authenticatedApi("/v1/preferences", {
    method: "PATCH",
    organizationId: input.organizationId,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      theme: input.theme === "radar-dark" ? "dark" : "light",
      accessibility: { density: input.density, reducedMotion: input.motion === "reduced" }
    })
  });
}
