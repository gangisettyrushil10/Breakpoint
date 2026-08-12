"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { Card } from "@/components/ui/primitives";
import { useAuth } from "@/components/AuthProvider";
import { useProfile } from "@/components/ProfileProvider";

type Mode = "signIn" | "signUp";

/**
 * Sign-in, sign-up, and sign-out on one route.
 *
 * Email and password rather than a magic link: a magic link cannot be tested or
 * used until SMTP is configured and deliverable, and an undeliverable link is
 * indistinguishable to the user from a broken app. Password auth works the
 * moment the project exists. Magic links remain a drop-in upgrade later.
 */
export default function AccountPage() {
  const { user, ready, enabled, signIn, signUp, signOut } = useAuth();
  const { hasOwnProfile, messages, syncError } = useProfile();

  const [mode, setMode] = useState<Mode>("signIn");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    setNotice(null);

    const result =
      mode === "signIn"
        ? await signIn(email, password)
        : await signUp(email, password);

    if (result.error) {
      setError(result.error);
    } else if ("needsConfirmation" in result && result.needsConfirmation) {
      setNotice(
        "Account created. Check your email for the confirmation link, then sign in. " +
          "(Turn off Confirm email in the Supabase dashboard to skip this step in development.)"
      );
    } else {
      setPassword("");
    }

    setBusy(false);
  }

  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-6 px-5 py-14">
      <div>
        <span className="label text-accent">Account</span>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">
          {user ? "Signed in" : "Save your stress test"}
        </h1>
        <p className="mt-2 text-[15px] leading-relaxed text-ink-2">
          {user
            ? "Your budget and chat history are stored in your account and follow you across devices."
            : "Signed out, everything stays in this browser on this device. Sign in to keep your budget and chat history across devices."}
        </p>
      </div>

      {!enabled ? (
        <Card>
          <p className="text-[15px] leading-relaxed text-ink-2">
            Accounts are not configured in this build. Set{" "}
            <code className="text-ink">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
            <code className="text-ink">NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY</code>{" "}
            in <code className="text-ink">apps/web/.env.local</code>. Everything
            else works without them — your data just stays in this browser.
          </p>
        </Card>
      ) : !ready ? (
        <Card>
          <p className="text-[15px] text-ink-2">Checking your session…</p>
        </Card>
      ) : user ? (
        <Card>
          <dl className="flex flex-col gap-3 text-[15px]">
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-ink-2">Email</dt>
              <dd className="truncate">{user.email}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-ink-2">Saved budget</dt>
              <dd>{hasOwnProfile ? "Yes" : "Not yet — using the demo"}</dd>
            </div>
            <div className="flex items-baseline justify-between gap-4">
              <dt className="text-ink-2">Chat messages</dt>
              <dd className="tnum">{messages.length}</dd>
            </div>
          </dl>

          <button
            type="button"
            onClick={() => void signOut()}
            className="mt-5 w-full rounded-md border border-line px-4 py-2 text-[15px] transition-colors hover:bg-surface-2"
          >
            Sign out
          </button>
        </Card>
      ) : (
        <Card>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5">
              <span className="label">Email</span>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                className="rounded-md border border-line bg-surface-2 px-3 py-2 text-[15px] outline-none focus:border-accent"
              />
            </label>

            <label className="flex flex-col gap-1.5">
              <span className="label">Password</span>
              <input
                type="password"
                required
                minLength={6}
                autoComplete={
                  mode === "signIn" ? "current-password" : "new-password"
                }
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="rounded-md border border-line bg-surface-2 px-3 py-2 text-[15px] outline-none focus:border-accent"
              />
            </label>

            <button
              type="submit"
              disabled={busy}
              className="rounded-md bg-accent px-4 py-2 text-[15px] font-medium text-bg transition-opacity disabled:opacity-50"
            >
              {busy
                ? "Working…"
                : mode === "signIn"
                  ? "Sign in"
                  : "Create account"}
            </button>

            <button
              type="button"
              onClick={() => {
                setMode(mode === "signIn" ? "signUp" : "signIn");
                setError(null);
                setNotice(null);
              }}
              className="text-[13px] text-ink-2 underline underline-offset-4 hover:text-ink"
            >
              {mode === "signIn"
                ? "No account yet? Create one"
                : "Already have an account? Sign in"}
            </button>
          </form>
        </Card>
      )}

      {error ? (
        <p className="text-[14px] text-critical" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="text-[14px] text-ink-2" role="status">
          {notice}
        </p>
      ) : null}
      {syncError ? (
        <p className="text-[14px] text-critical" role="alert">
          Sync problem: {syncError}
        </p>
      ) : null}

      <Link
        href="/"
        className="text-[13px] text-ink-2 underline underline-offset-4 hover:text-ink"
      >
        ← Back to the dashboard
      </Link>
    </main>
  );
}
