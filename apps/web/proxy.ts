import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

/**
 * Refreshes the Supabase session on every navigation.
 *
 * Access tokens are short-lived. Without a refresh point that can actually
 * write cookies, a signed-in user is quietly signed out the first time their
 * token expires mid-session -- and server components cannot set cookies
 * themselves, so this is the only place it can happen.
 *
 * Named `proxy` in `proxy.ts` because Next.js 16 deprecated the `middleware`
 * file convention and warns on it at build time.
 */
export async function proxy(request: NextRequest) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  // Supabase is optional: unconfigured builds fall back to browser storage and
  // must not be broken by auth middleware.
  if (!url || !publishableKey) return NextResponse.next();

  let response = NextResponse.next({ request });

  const supabase = createServerClient(url, publishableKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        // Written to both: the request so any downstream server render in this
        // same pass sees the refreshed token, and the response so the browser
        // actually keeps it.
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
      },
    },
  });

  // getUser(), not getSession(): this revalidates the token with the auth
  // server. getSession() only decodes whatever is in the cookie, which is
  // client-supplied and so not something to trust on the server.
  await supabase.auth.getUser();

  return response;
}

export const config = {
  matcher: [
    // Everything except static assets and image files -- those never carry a
    // session and would only add latency.
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
