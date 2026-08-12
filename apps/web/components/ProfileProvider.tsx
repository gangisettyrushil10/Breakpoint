"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "@/components/AuthProvider";
import { SIM_MONTHS, defaultProfile } from "@/lib/api/mappers";
import type { ChatMessage, FinancialProfile } from "@/lib/api/types";
import {
  browserStore,
  readLocalMessages,
  readLocalProfile,
  type Store,
} from "@/lib/storage";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import { createSupabaseStore } from "@/lib/supabase/store";

/**
 * The one profile the whole app talks about.
 *
 * This sits above the router so `/` and `/chat` are the same conversation about
 * the same budget: the agent's `patch_profile` edits land on the dashboard, and
 * the dashboard's profile is what the agent reasons about. Before this existed
 * the two routes were unrelated React trees, and chat silently discussed a
 * hardcoded demo profile.
 *
 * Which `Store` backs it depends on whether anyone is signed in, and that is
 * the only thing sign-in changes here. Nothing below this provider knows or
 * cares where the bytes live.
 */
interface ProfileContextValue {
  /** Always a valid profile — the demo one until the user saves their own. */
  profile: FinancialProfile;
  /** False while the user is looking at the demo budget rather than their own. */
  hasOwnProfile: boolean;
  setProfile: (profile: FinancialProfile) => void;
  /** True once the active store has been read. Nothing should simulate before this. */
  hydrated: boolean;
  months: number;
  messages: ChatMessage[];
  setMessages: (messages: ChatMessage[]) => void;
  clearAll: () => void;
  /**
   * Set when a write to the account failed. Surfaced rather than swallowed:
   * silently losing someone's budget is worse than telling them it did not save.
   */
  syncError: string | null;
}

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used within ProfileProvider");
  return ctx;
}

function message(error: unknown): string {
  return error instanceof Error ? error.message : "Could not save your changes.";
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { user, ready: authReady } = useAuth();
  const [profile, setProfileState] = useState<FinancialProfile>(defaultProfile);
  const [hasOwnProfile, setHasOwnProfile] = useState(false);
  const [messages, setMessagesState] = useState<ChatMessage[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  const store: Store = useMemo(() => {
    if (!user) return browserStore;
    return createSupabaseStore(getSupabaseBrowserClient(), user.id);
  }, [user]);

  /**
   * Writes are chained rather than fired in parallel.
   *
   * `supabaseStore.saveMessages` reads the stored count and then inserts the
   * tail beyond it. Two of those in flight at once would both read the same
   * count and both insert, duplicating a turn. Serialising is enough to prevent
   * it and costs nothing at human typing speed.
   */
  const queue = useRef<Promise<unknown>>(Promise.resolve());

  const enqueue = useCallback((work: () => Promise<unknown>) => {
    queue.current = queue.current
      .then(work)
      .catch((error: unknown) => setSyncError(message(error)));
  }, []);

  // Storage is read in an effect rather than in a `useState` initialiser so the
  // server and the first client render agree. Reading during render would make
  // the markup depend on localStorage or a session cookie, neither of which the
  // server can see — a hydration mismatch.
  //
  // This is the "subscribe to an external system" case the rule exempts in
  // principle but can't detect: the active store is unreadable until after
  // mount, so the one-shot setState is the synchronisation, not a cascade.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    // Waiting avoids a visible flash of the demo budget: without it the signed
    // out store loads first and is then replaced a moment later.
    if (!authReady) return;

    let active = true;
    setHydrated(false);

    async function hydrate() {
      let stored = await store.loadProfile();
      let transcript = await store.loadMessages();

      // First sign-in on a device that already has local work. Without this the
      // budget someone just spent ten minutes entering appears to vanish the
      // moment they make an account — the worst possible first impression of
      // signing in. Only ever an upload into an empty account, so it cannot
      // overwrite work done on another device.
      if (user && stored === null) {
        const local = readLocalProfile();
        if (local) {
          const localMessages = readLocalMessages();
          await store.saveProfile(local);
          await store.saveMessages(localMessages);
          stored = local;
          transcript = localMessages;
        }
      }

      if (!active) return;

      setProfileState(stored ?? defaultProfile);
      setHasOwnProfile(stored !== null);
      setMessagesState(transcript);
      setHydrated(true);
    }

    hydrate().catch((error: unknown) => {
      if (!active) return;
      // A failed read must not leave the app stuck on a spinner forever; fall
      // back to the demo profile and say what went wrong.
      setSyncError(message(error));
      setHydrated(true);
    });

    return () => {
      active = false;
    };
  }, [store, user, authReady]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const setProfile = useCallback(
    (next: FinancialProfile) => {
      setProfileState(next);
      setHasOwnProfile(true);
      setSyncError(null);
      enqueue(() => store.saveProfile(next));
    },
    [store, enqueue]
  );

  const setMessages = useCallback(
    (next: ChatMessage[]) => {
      setMessagesState(next);
      enqueue(() => store.saveMessages(next));
    },
    [store, enqueue]
  );

  const clearAll = useCallback(() => {
    setProfileState(defaultProfile);
    setHasOwnProfile(false);
    setMessagesState([]);
    setSyncError(null);
    enqueue(() => store.clearAll());
  }, [store, enqueue]);

  const value = useMemo(
    (): ProfileContextValue => ({
      profile,
      hasOwnProfile,
      setProfile,
      hydrated,
      months: SIM_MONTHS,
      messages,
      setMessages,
      clearAll,
      syncError,
    }),
    [
      profile,
      hasOwnProfile,
      setProfile,
      hydrated,
      messages,
      setMessages,
      clearAll,
      syncError,
    ]
  );

  return (
    <ProfileContext.Provider value={value}>{children}</ProfileContext.Provider>
  );
}
