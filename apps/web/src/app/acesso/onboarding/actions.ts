"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { authCookieOptions } from "@/lib/supabase/cookie-options";
import { getValidatedAccessToken } from "@/lib/server-api-client";

function text(formData: FormData, name: string) {
  const value = formData.get(name);
  return typeof value === "string" ? value.trim() : "";
}

export async function submitOnboarding(formData: FormData) {
  const displayName = text(formData, "displayName");
  const organizationName = text(formData, "organizationName");
  const organizationSlug = text(formData, "organizationSlug");
  const timezone = text(formData, "timezone") || "America/Sao_Paulo";
  const locale = text(formData, "locale") || "pt-BR";
  const goals = text(formData, "goals");
  const approvalPolicy = text(formData, "approvalPolicy");

  if (!displayName || !organizationName || !organizationSlug) redirect("/acesso/onboarding?error=missing_fields");

  const token = await getValidatedAccessToken();
  let parsedPolicy: Record<string, unknown> = {};
  if (approvalPolicy) {
    try {
      parsedPolicy = JSON.parse(approvalPolicy) as Record<string, unknown>;
    } catch {
      redirect("/acesso/onboarding?error=submit_failed");
    }
  }

  const apiUrl = process.env.API_URL?.replace(/\/$/, "");
  if (!apiUrl) redirect("/acesso/onboarding?error=submit_failed");

  const response = await fetch(`${apiUrl}/v1/onboarding`, {
    method: "POST",
    cache: "no-store",
    headers: {
      accept: "application/json",
      authorization: `Bearer ${token}`,
      "content-type": "application/json"
    },
    body: JSON.stringify({
      profile: { display_name: displayName, timezone, locale },
      organization: { name: organizationName, slug: organizationSlug, timezone, locale },
      goals: goals ? goals.split(",").map((item) => item.trim()).filter(Boolean) : [],
      approval_policy: parsedPolicy
    })
  });

  if (!response.ok) {
    redirect("/acesso/onboarding?error=submit_failed");
  }

  const payload = await response.json() as {
    organizationId?: string;
    organization_id?: string;
    nextRoute?: string;
    next_route?: string;
  };
  const organizationId = payload.organizationId ?? payload.organization_id;
  if (organizationId) {
    const store = await cookies();
    store.set("bighead-organization-id", organizationId, {
      httpOnly: true,
      sameSite: "lax",
      secure: authCookieOptions().secure,
      path: "/",
      maxAge: 60 * 60 * 24 * 30
    });
  }

  const requestedRoute = payload.nextRoute ?? payload.next_route;
  const nextRoute = typeof requestedRoute === "string" && requestedRoute.startsWith("/") ? requestedRoute : "/operacao/home";
  redirect(nextRoute);
}
