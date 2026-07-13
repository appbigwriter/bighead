import { NextResponse } from "next/server";

import { createClient } from "@/lib/supabase/server";

export async function POST(request: Request) {
  const supabase = await createClient();
  const { error } = await supabase.auth.signOut();
  if (error) {
    // Clear the browser session even when remote revocation is temporarily
    // unavailable, but never claim that global revocation succeeded.
    await supabase.auth.signOut({ scope: "local" });
    return NextResponse.redirect(
      new URL("/login?status=sign_out_incomplete", request.url),
      303
    );
  }
  return NextResponse.redirect(new URL("/login?status=signed_out", request.url), 303);
}
