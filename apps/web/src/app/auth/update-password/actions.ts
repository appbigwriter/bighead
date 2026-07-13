"use server";

import { redirect } from "next/navigation";

import { createClient } from "@/lib/supabase/server";

export async function updatePassword(formData: FormData) {
  const value = formData.get("password");
  const password = typeof value === "string" ? value : "";
  if (password.length < 12) redirect("/auth/update-password?error=weak_password");

  const supabase = await createClient();
  const { data: claimsData, error: claimsError } = await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) redirect("/auth/update-password?error=invalid_session");
  const { error } = await supabase.auth.updateUser({ password });
  if (error) redirect("/auth/update-password?error=invalid_session");
  redirect("/login?status=password_updated");
}
