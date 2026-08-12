"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { User } from "@supabase/supabase-js";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";
import { isSupabaseConfigured } from "@/lib/supabase/env";

/**
 * Who is signed in, if anyone.
 *
 * Signing in is optional by design. Without it the app is exactly what it was
 * before accounts existed -- a local, single-device stress test that keeps a
 * budget off someone else's server. `enabled: false` is the same story told by
 * a build that simply has no Supabase keys.
 */
interface AuthContextValue {
  user: User | null;
  /** False until the initial session lookup finishes. Don't read `user` before. */
  ready: boolean;
  /** Whether this build has Supabase keys at all. */
  enabled: boolean;
  signIn(email: string, password: string): Promise<{ error: string | null }>;
  signUp(
    email: string,
    password: string
  ): Promise<{ error: string | null; needsConfirmation: boolean }>;
  signOut(): Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(!isSupabaseConfigured);

  useEffect(() => {
    if (!isSupabaseConfigured) return;

    const supabase = getSupabaseBrowserClient();
    let active = true;

    // getUser() rather than getSession(): it revalidates against the auth
    // server, so a revoked or expired session is reported as signed out instead
    // of being trusted straight out of the cookie.
    supabase.auth.getUser().then(({ data }) => {
      if (!active) return;
      setUser(data.user ?? null);
      setReady(true);
    });

    // Covers sign-in, sign-out, and token refresh, including those performed in
    // another tab -- without this, a second tab keeps rendering a stale user.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!active) return;
      setUser(session?.user ?? null);
      setReady(true);
    });

    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const supabase = getSupabaseBrowserClient();
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });
    return { error: error?.message ?? null };
  }, []);

  const signUp = useCallback(async (email: string, password: string) => {
    const supabase = getSupabaseBrowserClient();
    const { data, error } = await supabase.auth.signUp({ email, password });

    if (error) return { error: error.message, needsConfirmation: false };

    // With "Confirm email" enabled on the project, signUp succeeds but returns
    // no session -- the account is real and unusable until the link is clicked.
    // Reporting that explicitly is the difference between a clear instruction
    // and an apparently successful sign-up that silently does nothing.
    return { error: null, needsConfirmation: data.session === null };
  }, []);

  const signOut = useCallback(async () => {
    const supabase = getSupabaseBrowserClient();
    await supabase.auth.signOut();
  }, []);

  const value = useMemo(
    (): AuthContextValue => ({
      user,
      ready,
      enabled: isSupabaseConfigured,
      signIn,
      signUp,
      signOut,
    }),
    [user, ready, signIn, signUp, signOut]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
