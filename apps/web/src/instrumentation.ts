export async function register() {
  if (process.env.NEXT_RUNTIME !== "nodejs") return;

  const [{ readSupabaseAuthRuntimeConfig }, { getSupabasePublicConfig }] = await Promise.all([
    import("./lib/supabase/auth-config"),
    import("./lib/supabase/config")
  ]);
  getSupabasePublicConfig();
  readSupabaseAuthRuntimeConfig();
}
