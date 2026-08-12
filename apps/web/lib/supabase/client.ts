"use client";

import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";
import { requireSupabaseEnv } from "./env";

/**
 * The browser-side Supabase client.
 *
 * Memoised because every `createBrowserClient` call installs its own auth
 * listener and token-refresh timer. Creating one per render would leave a
 * component's worth of orphaned refreshers behind on every re-render, and two
 * live clients can race each other writing the session cookie.
 */
let cached: SupabaseClient | null = null;

export function getSupabaseBrowserClient(): SupabaseClient {
  if (cached) return cached;

  const { url, publishableKey } = requireSupabaseEnv();
  cached = createBrowserClient(url, publishableKey);
  return cached;
}
