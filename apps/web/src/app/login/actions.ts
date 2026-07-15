"use server";

import { redirect } from "next/navigation";
import { cookies } from "next/headers";

import { createClient } from "@/lib/supabase/server";
import { readSupabaseAuthRuntimeConfig } from "@/lib/supabase/auth-config";
import { authCookieOptions } from "@/lib/supabase/cookie-options";
import { loginFailureLocation } from "./login-failure";

export async function signIn(formData: FormData) {
  const emailValue = formData.get("email");
  const passwordValue = formData.get("password");
  const email = typeof emailValue === "string" ? emailValue.trim() : "";
  const password = typeof passwordValue === "string" ? passwordValue : "";
  if (!email || !password) redirect("/login?error=missing_fields");

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) redirect(loginFailureLocation(error));

  const { data: organization } = await supabase.from("organizations").select("id").order("created_at").limit(1).maybeSingle();
  const organizationRecord: unknown = organization;
  const organizationId = organizationRecord !== null
    && typeof organizationRecord === "object"
    && "id" in organizationRecord
    && typeof organizationRecord.id === "string"
    ? organizationRecord.id
    : undefined;
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

  redirect("/operacao/home");
}

export async function signUp(formData: FormData) {
  const emailValue = formData.get("email");
  const passwordValue = formData.get("password");
  const email = typeof emailValue === "string" ? emailValue.trim() : "";
  const password = typeof passwordValue === "string" ? passwordValue : "";
  if (!email || !password) redirect("/login?error=missing_fields");

  const supabase = await createClient();
  const { data, error } = await supabase.auth.signUp({ email, password });
  if (error) redirect(loginFailureLocation(error));

  if (data.session) {
    const { data: organization } = await supabase.from("organizations").select("id").order("created_at").limit(1).maybeSingle();
    const organizationRecord: unknown = organization;
    const organizationId = organizationRecord !== null
      && typeof organizationRecord === "object"
      && "id" in organizationRecord
      && typeof organizationRecord.id === "string"
      ? organizationRecord.id
      : undefined;
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
    redirect("/operacao/home");
  }

  redirect("/login?status=signup_sent");
}

export async function requestMagicLink(formData: FormData) {
  const email = emailFrom(formData);
  if (!email) redirect("/login?error=missing_email");

  const { appUrl } = readSupabaseAuthRuntimeConfig();
  const supabase = await createClient();
  await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: `${appUrl}/auth/callback` }
  });
  redirect("/login?status=email_sent");
}

export async function requestPasswordReset(formData: FormData) {
  const email = emailFrom(formData);
  if (!email) redirect("/login?error=missing_email");

  const { appUrl } = readSupabaseAuthRuntimeConfig();
  const supabase = await createClient();
  await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${appUrl}/auth/callback?next=/auth/update-password`
  });
  redirect("/login?status=email_sent");
}

function emailFrom(formData: FormData) {
  const value = formData.get("email");
  return typeof value === "string" ? value.trim() : "";
}
