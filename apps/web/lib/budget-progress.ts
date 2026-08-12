/**
 * What the assistant knows about you so far, and what it is still missing.
 *
 * A conversation has no progress bar of its own, which is the one thing a form
 * is genuinely better at: you can see how much is left. This reconstructs that
 * signal without reintroducing the form — each answer lights up a row, and the
 * panel shows how close the picture is to complete.
 *
 * "Known" means the value differs from the demo budget. That is a heuristic, not
 * a fact: someone whose rent happens to match the example exactly reads as not
 * having answered. It is the right trade anyway — the alternative is tracking
 * provenance on every field through the agent, and being briefly wrong about one
 * row is much cheaper than that machinery.
 */

import { defaultProfile } from "@/lib/api/mappers";
import type { FinancialProfile } from "@/lib/api/types";
import type { GlossaryKey } from "@/lib/glossary";

export interface BudgetRow {
  id: string;
  /** Plain language. No money jargon on the surface. */
  label: string;
  cents: number;
  /** True once this differs from the example budget. */
  known: boolean;
  explain?: GlossaryKey;
}

export interface BudgetProgress {
  rows: BudgetRow[];
  known: number;
  total: number;
  /** 0–1, for the progress bar. */
  fraction: number;
}

function cents(profile: FinancialProfile, path: readonly string[]): number {
  return path.reduce<unknown>(
    (node, key) => (node as Record<string, unknown>)?.[key],
    profile
  ) as number;
}

/**
 * The rows worth showing, in roughly the order a conversation reaches them.
 *
 * Deliberately not all seventeen profile fields: a panel listing every one would
 * be the form again, in a narrower column. These are the figures that actually
 * move a breaking point.
 */
const FIELDS: ReadonlyArray<{
  id: string;
  label: string;
  path: readonly string[];
  explain?: GlossaryKey;
}> = [
  {
    id: "income",
    label: "Money coming in",
    path: ["income", "monthlyTakeHomeCents"],
  },
  { id: "rent", label: "Rent", path: ["expenses", "rentCents"] },
  { id: "food", label: "Food", path: ["expenses", "groceriesCents"] },
  {
    id: "transport",
    label: "Getting around",
    path: ["expenses", "transportationCents"],
  },
  {
    id: "bills",
    label: "Utilities",
    path: ["expenses", "utilitiesCents"],
  },
  {
    id: "debt",
    label: "Debt payments",
    path: ["debt", "minimumPaymentsCents"],
    explain: "debtMinimums",
  },
  {
    id: "card",
    label: "Owed on cards",
    path: ["debt", "creditCardBalanceCents"],
  },
  {
    id: "savings",
    label: "Savings you can reach",
    path: ["savings", "liquidCents"],
    explain: "liquidSavings",
  },
];

export function budgetProgress(profile: FinancialProfile): BudgetProgress {
  const rows: BudgetRow[] = FIELDS.map((field) => ({
    id: field.id,
    label: field.label,
    cents: cents(profile, field.path),
    known: cents(profile, field.path) !== cents(defaultProfile, field.path),
    explain: field.explain,
  }));

  const known = rows.filter((row) => row.known).length;

  return {
    rows,
    known,
    total: rows.length,
    fraction: rows.length === 0 ? 0 : known / rows.length,
  };
}
