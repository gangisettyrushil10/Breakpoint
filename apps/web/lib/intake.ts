/**
 * Form draft <-> `FinancialProfile` conversion.
 *
 * Two rules the rest of the app depends on:
 *
 * * **Dollars at the input boundary, integer cents everywhere else.** The
 *   contract is cents (ARCHITECTURE.md, principle 1) precisely so no float ever
 *   reaches the engine; the form is the single place the conversion happens.
 * * **The constraints mirror `app/domain/financial_profile.py`.** They are
 *   duplicated on purpose — the server still validates, but a user should not
 *   have to make a round trip to be told their rent can't be negative. If the
 *   pydantic model changes, change these too.
 *
 * Kept separate from the component so the conversion is testable without React.
 */

import type { FinancialProfile, JobStability, PayFrequency } from "@/lib/api/types";

/** A dotted path into the profile, e.g. `expenses.rentCents`. */
export type DraftKey = string;
export type Draft = Record<DraftKey, string>;
export type FieldErrors = Record<DraftKey, string>;

export interface MoneyField {
  key: DraftKey;
  label: string;
  hint?: string;
  /** Money must be > 0 rather than >= 0 (income is the only one). */
  positive?: boolean;
}

export interface FieldGroup {
  id: keyof FinancialProfile & string;
  title: string;
  lede: string;
  money: MoneyField[];
}

/** The money fields, grouped exactly as the schema groups them. */
export const MONEY_GROUPS: FieldGroup[] = [
  {
    id: "income",
    title: "Income",
    lede: "What actually lands in your account — after tax, after deductions.",
    money: [
      {
        key: "income.monthlyTakeHomeCents",
        label: "Monthly take-home",
        hint: "If you're paid biweekly, use your typical month.",
        positive: true,
      },
    ],
  },
  {
    id: "expenses",
    title: "Monthly expenses",
    lede: "The engine treats rent, utilities, insurance and debt minimums as fixed, and subscriptions and discretionary as cuttable.",
    money: [
      { key: "expenses.rentCents", label: "Rent or mortgage" },
      { key: "expenses.utilitiesCents", label: "Utilities" },
      { key: "expenses.groceriesCents", label: "Groceries" },
      { key: "expenses.transportationCents", label: "Transportation" },
      { key: "expenses.insuranceCents", label: "Insurance" },
      { key: "expenses.otherEssentialCents", label: "Other essential" },
      {
        key: "expenses.subscriptionsCents",
        label: "Subscriptions",
        hint: "Counted as cuttable in the prevention plan.",
      },
      {
        key: "expenses.discretionaryCents",
        label: "Discretionary",
        hint: "Also counted as cuttable.",
      },
    ],
  },
  {
    id: "debt",
    title: "Debt and credit",
    lede: "Credit delays a breaking point rather than preventing one, so the limit matters as much as the balance.",
    money: [
      {
        key: "debt.minimumPaymentsCents",
        label: "Monthly debt minimums",
        hint: "These keep running even when income stops.",
      },
      { key: "debt.creditCardBalanceCents", label: "Credit card balance" },
      {
        key: "debt.availableCreditCents",
        label: "Available credit",
        hint: "How much you could still draw, not the total limit.",
      },
    ],
  },
  {
    id: "savings",
    title: "Savings",
    lede: "Only money you could actually reach this week. Retirement accounts don't count.",
    money: [{ key: "savings.liquidCents", label: "Liquid savings" }],
  },
];

export const PAY_FREQUENCIES: { value: PayFrequency; label: string }[] = [
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "Every two weeks" },
  { value: "semimonthly", label: "Twice a month" },
  { value: "monthly", label: "Monthly" },
];

export const JOB_STABILITIES: { value: JobStability; label: string }[] = [
  { value: "stable", label: "Stable — salaried or long-tenured" },
  { value: "contract", label: "Contract or gig" },
  { value: "unstable", label: "Unstable — at risk or seasonal" },
];

const ALL_MONEY_FIELDS = MONEY_GROUPS.flatMap((group) => group.money);

function get(profile: FinancialProfile, path: DraftKey): unknown {
  return path
    .split(".")
    .reduce<unknown>(
      (node, key) =>
        typeof node === "object" && node !== null
          ? (node as Record<string, unknown>)[key]
          : undefined,
      profile
    );
}

/** Seed the form from an existing profile — dollars as plain decimal strings. */
export function profileToDraft(profile: FinancialProfile): Draft {
  const draft: Draft = {
    "location.city": profile.location.city,
    "location.state": profile.location.state,
    "location.postalCode": profile.location.postalCode,
    "household.dependents": String(profile.household.dependents),
    "household.jobStability": profile.household.jobStability,
    "income.payFrequency": profile.income.payFrequency,
    "debt.creditAprBps": (profile.debt.creditAprBps / 100).toFixed(2),
  };

  for (const field of ALL_MONEY_FIELDS) {
    const cents = get(profile, field.key);
    draft[field.key] = typeof cents === "number" ? (cents / 100).toFixed(2) : "";
  }

  return draft;
}

/**
 * Dollars string -> integer cents.
 *
 * `Math.round` rather than a truncation: "1650.005" should not silently become
 * $1650.00, and float multiplication of e.g. 18.5 * 100 lands on 1849.9999...
 */
function parseMoney(raw: string): number | null {
  const cleaned = raw.replace(/[$,\s]/g, "");
  if (cleaned === "") return null;
  if (!/^-?\d*\.?\d*$/.test(cleaned)) return null;
  const value = Number.parseFloat(cleaned);
  if (!Number.isFinite(value)) return null;
  return Math.round(value * 100);
}

export interface ConversionResult {
  profile: FinancialProfile | null;
  errors: FieldErrors;
}

/** Validate a draft and build a profile, or report per-field errors. */
export function draftToProfile(draft: Draft): ConversionResult {
  const errors: FieldErrors = {};
  const cents: Record<DraftKey, number> = {};

  for (const field of ALL_MONEY_FIELDS) {
    const parsed = parseMoney(draft[field.key] ?? "");
    if (parsed === null) {
      errors[field.key] = "Enter an amount.";
      continue;
    }
    if (parsed < 0) {
      errors[field.key] = "Can't be negative.";
      continue;
    }
    if (field.positive && parsed === 0) {
      errors[field.key] = "Must be more than $0.";
      continue;
    }
    cents[field.key] = parsed;
  }

  const city = (draft["location.city"] ?? "").trim();
  if (!city) errors["location.city"] = "Enter a city.";

  const state = (draft["location.state"] ?? "").trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(state)) {
    errors["location.state"] = "Two-letter state code.";
  }

  const postalCode = (draft["location.postalCode"] ?? "").trim();
  if (!postalCode) errors["location.postalCode"] = "Enter a ZIP code.";

  const dependents = Number.parseInt(draft["household.dependents"] ?? "", 10);
  if (!Number.isInteger(dependents) || dependents < 0) {
    errors["household.dependents"] = "Enter 0 or more.";
  }

  // The engine takes basis points; the form asks for a percentage because
  // nobody reads their statement in bps. 0–100% maps to the model's 0–10000.
  const aprPercent = Number.parseFloat(draft["debt.creditAprBps"] ?? "");
  if (!Number.isFinite(aprPercent) || aprPercent < 0 || aprPercent > 100) {
    errors["debt.creditAprBps"] = "Enter an APR between 0 and 100.";
  }

  if (Object.keys(errors).length > 0) return { profile: null, errors };

  return {
    profile: {
      schemaVersion: 1,
      currency: "USD",
      location: { city, state, postalCode },
      household: {
        dependents,
        jobStability: (draft["household.jobStability"] ?? "stable") as JobStability,
      },
      income: {
        monthlyTakeHomeCents: cents["income.monthlyTakeHomeCents"],
        payFrequency: (draft["income.payFrequency"] ?? "monthly") as PayFrequency,
      },
      expenses: {
        rentCents: cents["expenses.rentCents"],
        utilitiesCents: cents["expenses.utilitiesCents"],
        groceriesCents: cents["expenses.groceriesCents"],
        transportationCents: cents["expenses.transportationCents"],
        insuranceCents: cents["expenses.insuranceCents"],
        subscriptionsCents: cents["expenses.subscriptionsCents"],
        discretionaryCents: cents["expenses.discretionaryCents"],
        otherEssentialCents: cents["expenses.otherEssentialCents"],
      },
      debt: {
        minimumPaymentsCents: cents["debt.minimumPaymentsCents"],
        creditCardBalanceCents: cents["debt.creditCardBalanceCents"],
        availableCreditCents: cents["debt.availableCreditCents"],
        creditAprBps: Math.round(aprPercent * 100),
      },
      savings: { liquidCents: cents["savings.liquidCents"] },
    },
    errors,
  };
}
