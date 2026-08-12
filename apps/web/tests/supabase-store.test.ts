import { describe, expect, it, beforeEach } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import type { ChatMessage, FinancialProfile } from "@/lib/api/types";
import { createSupabaseStore } from "@/lib/supabase/store";
import { FakeSupabase } from "./fakes/supabase";

const USER = "11111111-1111-4111-8111-111111111111";

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

const turn = (role: ChatMessage["role"], content: string): ChatMessage => ({
  role,
  content,
});

let db: FakeSupabase;
const store = () => createSupabaseStore(db as unknown as SupabaseClient, USER);

beforeEach(() => {
  db = new FakeSupabase();
});

describe("profile", () => {
  it("returns null for an account that has never saved one", async () => {
    expect(await store().loadProfile()).toBeNull();
  });

  it("round-trips a saved profile", async () => {
    await store().saveProfile(PROFILE);
    expect(await store().loadProfile()).toEqual(PROFILE);
  });

  it("replaces rather than duplicating on repeated saves", async () => {
    const s = store();
    await s.saveProfile(PROFILE);
    await s.saveProfile({ ...PROFILE, savings: { liquidCents: 1 } });

    expect(db.rowsIn("profiles")).toHaveLength(1);
    expect((await s.loadProfile())?.savings.liquidCents).toBe(1);
  });

  it("treats a structurally invalid stored row as absent", async () => {
    // A row written by an older build. Returning it would push a malformed
    // profile into the charts, which is the failure the guard exists to stop.
    db.rowsIn("profiles").push({
      user_id: USER,
      profile: { schemaVersion: 1, currency: "USD" },
    });

    expect(await store().loadProfile()).toBeNull();
  });

  it("surfaces an unexpected read failure instead of reporting no profile", async () => {
    db.failNext = { message: "connection reset", code: "57P01" };
    await expect(store().loadProfile()).rejects.toMatchObject({
      message: "connection reset",
    });
  });
});

describe("transcript", () => {
  it("persists a first exchange and reads it back in order", async () => {
    const s = store();
    const messages = [
      turn("user", "what if i lose my job"),
      turn("assistant", "Let me simulate that."),
    ];

    await s.saveMessages(messages);
    expect(await s.loadMessages()).toEqual(messages);
  });

  it("appends only the new turn instead of rewriting the conversation", async () => {
    const s = store();
    const first = [turn("user", "one"), turn("assistant", "two")];
    await s.saveMessages(first);

    const idsAfterFirst = db.rowsIn("chat_messages").map((row) => row.id);

    await s.saveMessages([...first, turn("user", "three")]);

    const rows = db.rowsIn("chat_messages");
    expect(rows).toHaveLength(3);
    // The original rows keep their identities: they were left alone, not
    // deleted and re-inserted.
    expect(rows.slice(0, 2).map((row) => row.id)).toEqual(idsAfterFirst);
  });

  it("does nothing when the transcript has not changed", async () => {
    const s = store();
    const messages = [turn("user", "one")];

    await s.saveMessages(messages);
    await s.saveMessages(messages);

    expect(db.rowsIn("chat_messages")).toHaveLength(1);
  });

  it("rewrites when the transcript shrinks", async () => {
    const s = store();
    await s.saveMessages([turn("user", "one"), turn("assistant", "two")]);
    await s.saveMessages([turn("user", "restarted")]);

    expect(await s.loadMessages()).toEqual([turn("user", "restarted")]);
    expect(db.rowsIn("chat_messages")).toHaveLength(1);
  });

  it("does not duplicate the transcript when the store is recreated", async () => {
    // The regression guard for remembering the synced count in a closure: a new
    // store instance (a provider remount) must not re-insert what is already
    // stored.
    const first = [turn("user", "one"), turn("assistant", "two")];
    await store().saveMessages(first);

    const remounted = store();
    await remounted.saveMessages([...first, turn("user", "three")]);

    expect(db.rowsIn("chat_messages")).toHaveLength(3);
    expect(await remounted.loadMessages()).toEqual([
      ...first,
      turn("user", "three"),
    ]);
  });

  it("keeps an empty transcript empty", async () => {
    await store().saveMessages([]);
    expect(db.rowsIn("chat_messages")).toHaveLength(0);
  });
});

describe("clearAll", () => {
  it("removes both the profile and the transcript", async () => {
    const s = store();
    await s.saveProfile(PROFILE);
    await s.saveMessages([turn("user", "one")]);

    await s.clearAll();

    expect(db.rowsIn("profiles")).toHaveLength(0);
    expect(db.rowsIn("chat_messages")).toHaveLength(0);
    expect(await s.loadProfile()).toBeNull();
  });
});

describe("user scoping", () => {
  it("does not read another user's rows", async () => {
    await store().saveProfile(PROFILE);

    const other = createSupabaseStore(
      db as unknown as SupabaseClient,
      "22222222-2222-4222-8222-222222222222"
    );

    expect(await other.loadProfile()).toBeNull();
    expect(await other.loadMessages()).toEqual([]);
  });
});
