/**
 * Local persistence for the working profile and the chat transcript.
 *
 * The API is stateless on purpose — the client owns the conversation and resends
 * it every turn. That makes the browser a natural home for it, and it keeps a
 * budget off someone else's server, which is the privacy risk ARCHITECTURE.md
 * names. The cost is honest and worth stating: single device, no sharing.
 *
 * That cost is what `supabaseStore` (lib/supabase/store.ts) buys back, and only
 * for users who sign in and ask for it. Signed out, nothing leaves the browser
 * and this module is still the whole story.
 *
 * Everything goes through the `Store` interface so swapping in a real backend
 * later is a new implementation rather than a hunt through components. Nothing
 * outside this module should touch `localStorage` directly.
 */

import type { ChatMessage, FinancialProfile } from "@/lib/api/types";

/** Bumped when a stored shape stops being readable. Stale data is dropped. */
export const STORAGE_VERSION = 1;

const PROFILE_KEY = `breakpoint.profile.v${STORAGE_VERSION}`;
const CHAT_KEY = `breakpoint.chat.v${STORAGE_VERSION}`;

/**
 * Every method is async even though `browserStore` answers instantly.
 *
 * The alternative — a sync interface plus a parallel async one — would push the
 * choice between them into every component, which is exactly the hunt through
 * components this indirection exists to prevent. One awaited shape means a
 * caller never has to know which backend it got.
 */
export interface Store {
  loadProfile(): Promise<FinancialProfile | null>;
  saveProfile(profile: FinancialProfile): Promise<void>;
  loadMessages(): Promise<ChatMessage[]>;
  saveMessages(messages: ChatMessage[]): Promise<void>;
  clearAll(): Promise<void>;
}

/**
 * Structural check before trusting anything off the wire or out of storage.
 *
 * Deliberately mirrors the pydantic model in
 * `services/api/app/domain/financial_profile.py` rather than trusting a cast:
 * a half-written or hand-edited entry would otherwise surface as a crash deep
 * inside a chart, far from the cause.
 */
export function isFinancialProfile(value: unknown): value is FinancialProfile {
  if (typeof value !== "object" || value === null) return false;
  const p = value as Record<string, unknown>;

  if (p.schemaVersion !== 1 || p.currency !== "USD") return false;

  const groups: Record<string, string[]> = {
    location: [],
    household: ["dependents"],
    income: ["monthlyTakeHomeCents"],
    expenses: [
      "rentCents",
      "utilitiesCents",
      "groceriesCents",
      "transportationCents",
      "insuranceCents",
      "subscriptionsCents",
      "discretionaryCents",
      "otherEssentialCents",
    ],
    debt: [
      "minimumPaymentsCents",
      "creditCardBalanceCents",
      "availableCreditCents",
      "creditAprBps",
    ],
    savings: ["liquidCents"],
  };

  for (const [group, numericFields] of Object.entries(groups)) {
    const node = p[group];
    if (typeof node !== "object" || node === null) return false;
    const record = node as Record<string, unknown>;
    for (const field of numericFields) {
      if (typeof record[field] !== "number" || !Number.isFinite(record[field])) {
        return false;
      }
    }
  }

  const location = p.location as Record<string, unknown>;
  return (
    typeof location.city === "string" &&
    typeof location.state === "string" &&
    typeof location.postalCode === "string"
  );
}

function isMessageArray(value: unknown): value is ChatMessage[] {
  return (
    Array.isArray(value) &&
    value.every((item) => {
      if (typeof item !== "object" || item === null) return false;
      const m = item as Record<string, unknown>;
      return (
        (m.role === "user" || m.role === "assistant") &&
        typeof m.content === "string"
      );
    })
  );
}

/**
 * `localStorage` throws rather than returning null in two ordinary situations —
 * Safari private browsing, and a full quota — so every access is guarded. A
 * storage failure must never take the app down with it; the worst acceptable
 * outcome is that this session doesn't persist.
 */
function read<T>(key: string, guard: (value: unknown) => value is T): T | null {
  if (typeof window === "undefined") return null;

  let raw: string | null;
  try {
    raw = window.localStorage.getItem(key);
  } catch {
    return null;
  }
  if (raw === null) return null;

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    remove(key);
    return null;
  }

  if (!guard(parsed)) {
    // Written by an older build, or hand-edited. Drop it rather than letting a
    // malformed profile reach the charts.
    remove(key);
    return null;
  }

  return parsed;
}

function write(key: string, value: unknown): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Quota exceeded or storage disabled. Nothing useful to do — the session
    // still works, it just won't survive a refresh.
  }
}

function remove(key: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(key);
  } catch {
    /* see write() */
  }
}

export const browserStore: Store = {
  loadProfile: async () => read(PROFILE_KEY, isFinancialProfile),
  saveProfile: async (profile) => write(PROFILE_KEY, profile),
  loadMessages: async () => read(CHAT_KEY, isMessageArray) ?? [],
  saveMessages: async (messages) => write(CHAT_KEY, messages),
  clearAll: async () => {
    remove(PROFILE_KEY);
    remove(CHAT_KEY);
  },
};

/** Exported for the sign-in handoff, which needs to know whether there is any
 *  local work worth carrying up to the account before it is discarded. */
export function readLocalProfile(): FinancialProfile | null {
  return read(PROFILE_KEY, isFinancialProfile);
}

export function readLocalMessages(): ChatMessage[] {
  return read(CHAT_KEY, isMessageArray) ?? [];
}
