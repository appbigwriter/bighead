import { NextResponse, type NextRequest } from "next/server";

import { readSupabaseAuthRuntimeConfig, safeInternalRedirect } from "@/lib/supabase/auth-config";
import { createClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const destination = safeInternalRedirect(request.nextUrl.searchParams.get("next"));
  const { appUrl } = readSupabaseAuthRuntimeConfig();

  if (!code) return NextResponse.redirect(`${appUrl}/login?error=invalid_callback`);

  const supabase = await createClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) return NextResponse.redirect(`${appUrl}/login?error=invalid_callback`);

  return NextResponse.redirect(new URL(destination, appUrl));
}
