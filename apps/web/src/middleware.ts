import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { getSupabasePublicConfig } from "./lib/supabase/config";
import { authCookieOptions, protectedAuthCookieOptions } from "./lib/supabase/cookie-options";
import { shouldUseMockWorkspace } from "./lib/workspace-mode";

export async function middleware(request: NextRequest) {
  if (shouldUseMockWorkspace()) {
    return NextResponse.next({ request });
  }

  const { url, publishableKey } = getSupabasePublicConfig();
  let response = NextResponse.next({ request });
  const supabase = createServerClient(url, publishableKey, {
    cookieOptions: authCookieOptions(),
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (cookiesToSet, responseHeaders) => {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, protectedAuthCookieOptions(options)));
        Object.entries(responseHeaders).forEach(([name, value]) => response.headers.set(name, value));
      }
    }
  });

  await supabase.auth.getClaims();
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"]
};
