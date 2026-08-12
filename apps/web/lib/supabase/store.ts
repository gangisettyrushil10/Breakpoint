/**
 * The signed-in implementation of `Store`, backed by Postgres instead of
 * `localStorage`. Same contract, so nothing above it changes shape.
 *
 * Every statement here is scoped by `user_id`, which looks redundant next to
 * row-level security and is not: RLS is the thing that actually enforces
 * ownership, and these filters are what keep an accidental cross-user query
 * from silently returning nothing and reading as "no data" instead of "bug".
 *
 * Reads are validated with the same `isFinancialProfile` guard used on
 * localStorage. A row written by an older build is exactly as untrustworthy as
 * a hand-edited storage entry, and the failure it causes -- a crash deep inside
 * a chart -- is identical.
 */

import type { SupabaseClient } from "@supabase/supabase-js";
import type { ChatMessage, FinancialProfile } from "@/lib/api/types";
import { isFinancialProfile, type Store } from "@/lib/storage";

/** Postgres error code for "no rows returned" from `.single()`. */
const NO_ROWS = "PGRST116";

export function createSupabaseStore(
  client: SupabaseClient,
  userId: string
): Store {
  async function messageCount(): Promise<number> {
    const { count, error } = await client
      .from("chat_messages")
      .select("id", { count: "exact", head: true })
      .eq("user_id", userId);

    if (error) throw error;
    return count ?? 0;
  }

  async function deleteAllMessages(): Promise<void> {
    const { error } = await client
      .from("chat_messages")
      .delete()
      .eq("user_id", userId);

    if (error) throw error;
  }

  async function insertMessages(messages: ChatMessage[]): Promise<void> {
    if (messages.length === 0) return;

    const { error } = await client.from("chat_messages").insert(
      messages.map((message) => ({
        user_id: userId,
        role: message.role,
        content: message.content,
      }))
    );

    if (error) throw error;
  }

  return {
    async loadProfile() {
      const { data, error } = await client
        .from("profiles")
        .select("profile")
        .eq("user_id", userId)
        .single();

      // A brand-new account legitimately has no row. Everything else is a real
      // failure and should surface rather than read as "no saved profile".
      if (error) {
        if (error.code === NO_ROWS) return null;
        throw error;
      }

      const stored = data?.profile;
      return isFinancialProfile(stored) ? stored : null;
    },

    async saveProfile(profile: FinancialProfile) {
      const { error } = await client
        .from("profiles")
        .upsert(
          { user_id: userId, profile },
          { onConflict: "user_id" }
        );

      if (error) throw error;
    },

    async loadMessages() {
      const { data, error } = await client
        .from("chat_messages")
        .select("role, content")
        .eq("user_id", userId)
        // The identity column, not created_at: two messages written in the same
        // millisecond would otherwise come back in an arbitrary order, which on
        // a transcript means the reply can precede the question.
        .order("id", { ascending: true });

      if (error) throw error;

      return (data ?? []).map((row) => ({
        role: row.role as ChatMessage["role"],
        content: row.content as string,
      }));
    },

    /**
     * Transcripts only ever grow, so the common path inserts just the new tail
     * rather than rewriting the conversation on every turn.
     *
     * The count is re-read from the database instead of being remembered in a
     * closure, because this store is recreated whenever the provider remounts.
     * A remembered count would restart at zero and re-insert the entire
     * transcript as duplicates.
     */
    async saveMessages(messages: ChatMessage[]) {
      const stored = await messageCount();

      if (messages.length === stored) return;

      // Shrunk: the transcript was cleared or rolled back, so the stored tail no
      // longer corresponds to anything. Rewrite rather than guess.
      if (messages.length < stored) {
        await deleteAllMessages();
        await insertMessages(messages);
        return;
      }

      await insertMessages(messages.slice(stored));
    },

    async clearAll() {
      await deleteAllMessages();

      const { error } = await client
        .from("profiles")
        .delete()
        .eq("user_id", userId);

      if (error) throw error;
    },
  };
}
