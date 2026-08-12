import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { requireSupabaseEnv } from "./env";

/**
 * Supabase client for server components, route handlers, and server actions.
 *
 * A new client per request, never a module-level singleton: it closes over one
 * request's cookies, so sharing it across requests would serve one user's
 * session to another.
 */
export async function createSupabaseServerClient() {
  const { url, publishableKey } = requireSupabaseEnv();
  const cookieStore = await cookies();

  return createServerClient(url, publishableKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Server components cannot set cookies. This is expected and safe to
          // swallow *only* because middleware refreshes the session on every
          // matched request; without that, sessions would expire silently.
        }
      },
    },
  });
}
