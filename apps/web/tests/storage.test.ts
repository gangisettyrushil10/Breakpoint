/**
 * `browserStore` is the signed-out half of the `Store` contract, and the half
 * that still runs for every user who never makes an account. These tests cover
 * the two things it promises beyond "write it down": that it refuses to hand
 * back a malformed profile, and that a storage failure degrades the session
 * rather than taking the app with it.
 */

import { describe, expect, it, beforeEach } from "vitest";
import type { FinancialProfile } from "@/lib/api/types";

const PROFILE: FinancialProfile = {
  schemaVersion: 1,
  currency: "USD",
  location: { city: "Austin", state: "TX", postalCode: "78701" },
  household: { dependents: 0, jobStability: "stable" },
  income: { monthlyTakeHomeCents: 435000, payFrequency: "biweekly" },
  expenses: {
    rentCents: 155000,
    utilitiesCents: 22000,
    groceriesCents: 48000,
    transportationCents: 31000,
    insuranceCents: 18000,
    subscriptionsCents: 6000,
    discretionaryCents: 40000,
    otherEssentialCents: 9000,
  },
  debt: {
    minimumPaymentsCents: 24000,
    creditCardBalanceCents: 310000,
    availableCreditCents: 690000,
    creditAprBps: 2440,
  },
  savings: { liquidCents: 520000 },
};

class FakeStorage {
  map = new Map<string, string>();
  /** Set to emulate Safari private browsing or an exceeded quota. */
  throwOnWrite = false;
  throwOnRead = false;

  getItem(key: string): string | null {
    if (this.throwOnRead) throw new Error("storage disabled");
    return this.map.has(key) ? this.map.get(key)! : null;
  }

  setItem(key: string, value: string): void {
    if (this.throwOnWrite) throw new Error("quota exceeded");
    this.map.set(key, value);
  }

  removeItem(key: string): void {
    this.map.delete(key);
  }
}

let storage: FakeStorage;

beforeEach(() => {
  storage = new FakeStorage();
  // storage.ts guards on `typeof window === "undefined"`, so a bare object with
  // a localStorage is all it needs to consider itself in a browser.
  (globalThis as { window?: unknown }).window = { localStorage: storage };
});

async function freshStore() {
  // Re-imported per test so the module-level key constants are rebuilt against
  // the current fake.
  const { browserStore } = await import("@/lib/storage");
  return browserStore;
}

const PROFILE_KEY = "breakpoint.profile.v1";
const CHAT_KEY = "breakpoint.chat.v1";

describe("browserStore", () => {
  it("round-trips a profile", async () => {
    const store = await freshStore();
    await store.saveProfile(PROFILE);
    expect(await store.loadProfile()).toEqual(PROFILE);
  });

  it("reports no profile when nothing has been saved", async () => {
    const store = await freshStore();
    expect(await store.loadProfile()).toBeNull();
  });

  it("defaults to an empty transcript", async () => {
    const store = await freshStore();
    expect(await store.loadMessages()).toEqual([]);
  });

  it("round-trips a transcript", async () => {
    const store = await freshStore();
    const messages = [
      { role: "user" as const, content: "one" },
      { role: "assistant" as const, content: "two" },
    ];
    await store.saveMessages(messages);
    expect(await store.loadMessages()).toEqual(messages);
  });

  it("drops and deletes a structurally invalid profile", async () => {
    const store = await freshStore();
    storage.map.set(PROFILE_KEY, JSON.stringify({ schemaVersion: 1 }));

    expect(await store.loadProfile()).toBeNull();
    // Deleted, not merely ignored: leaving it would re-run the same rejection
    // on every load.
    expect(storage.map.has(PROFILE_KEY)).toBe(false);
  });

  it("drops a profile written under a different schema version", async () => {
    const store = await freshStore();
    storage.map.set(PROFILE_KEY, JSON.stringify({ ...PROFILE, schemaVersion: 2 }));

    expect(await store.loadProfile()).toBeNull();
  });

  it("drops unparseable JSON", async () => {
    const store = await freshStore();
    storage.map.set(PROFILE_KEY, "{not json");

    expect(await store.loadProfile()).toBeNull();
    expect(storage.map.has(PROFILE_KEY)).toBe(false);
  });

  it("rejects a transcript containing a non-message", async () => {
    const store = await freshStore();
    storage.map.set(CHAT_KEY, JSON.stringify([{ role: "system", content: "x" }]));

    expect(await store.loadMessages()).toEqual([]);
  });

  it("survives a write to full or disabled storage", async () => {
    const store = await freshStore();
    storage.throwOnWrite = true;

    // The worst acceptable outcome is that this session does not persist -- not
    // an exception escaping into a render.
    await expect(store.saveProfile(PROFILE)).resolves.toBeUndefined();
  });

  it("survives a read from disabled storage", async () => {
    const store = await freshStore();
    storage.throwOnRead = true;

    expect(await store.loadProfile()).toBeNull();
  });

  it("clears both keys", async () => {
    const store = await freshStore();
    await store.saveProfile(PROFILE);
    await store.saveMessages([{ role: "user", content: "one" }]);

    await store.clearAll();

    expect(await store.loadProfile()).toBeNull();
    expect(await store.loadMessages()).toEqual([]);
  });
});
