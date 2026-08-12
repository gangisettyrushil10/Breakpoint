/**
 * Supabase connection values, read in one place.
 *
 * Both are `NEXT_PUBLIC_*` and therefore compiled into the browser bundle. That
 * is correct for the publishable key and would be a breach for the secret one:
 * what protects a row here is row-level security, not the obscurity of the key.
 * Nothing in `apps/web` should ever read a Supabase secret.
 *
 * The references below are written out literally because Next.js inlines
 * `process.env.NEXT_PUBLIC_*` at build time by textual substitution -- a
 * computed lookup would silently produce `undefined` in the browser.
 */

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const publishableKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

/**
 * Whether this build can talk to Supabase at all.
 *
 * Kept as a boolean rather than letting a missing value throw, because running
 * without Supabase is a supported mode: the app falls back to `browserStore`
 * and behaves exactly as it did before accounts existed. A contributor who has
 * not been given project keys should still get a working dashboard.
 */
export const isSupabaseConfigured = Boolean(url && publishableKey);

export function requireSupabaseEnv(): { url: string; publishableKey: string } {
  if (!url || !publishableKey) {
    throw new Error(
      "Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and " +
        "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY in apps/web/.env.local, or use " +
        "the app signed out -- it falls back to browser storage."
    );
  }

  return { url, publishableKey };
}
