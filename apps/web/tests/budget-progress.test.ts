/**
 * The panel's progress signal.
 *
 * A conversation has no natural sense of "how much is left", so this
 * reconstructs one by diffing against the demo budget. The heuristic and its
 * known blind spot are both pinned here, so the blind spot stays a decision
 * rather than becoming a surprise.
 */

import { describe, expect, it } from "vitest";
import { budgetProgress } from "@/lib/budget-progress";
import { defaultProfile } from "@/lib/api/mappers";
import type { FinancialProfile } from "@/lib/api/types";

const edited = (patch: (p: FinancialProfile) => void): FinancialProfile => {
  const next = structuredClone(defaultProfile);
  patch(next);
  return next;
};

describe("budgetProgress", () => {
  it("knows nothing about an untouched demo budget", () => {
    const progress = budgetProgress(defaultProfile);

    expect(progress.known).toBe(0);
    expect(progress.fraction).toBe(0);
    expect(progress.rows.every((row) => !row.known)).toBe(true);
  });

  it("counts a field as known once it differs from the example", () => {
    const progress = budgetProgress(
      edited((p) => {
        p.income.monthlyTakeHomeCents = 412_000;
      })
    );

    expect(progress.known).toBe(1);
    expect(progress.rows.find((row) => row.id === "income")?.known).toBe(true);
    expect(progress.rows.find((row) => row.id === "rent")?.known).toBe(false);
  });

  it("advances as more is answered", () => {
    const one = budgetProgress(
      edited((p) => {
        p.income.monthlyTakeHomeCents = 412_000;
      })
    );
    const three = budgetProgress(
      edited((p) => {
        p.income.monthlyTakeHomeCents = 412_000;
        p.expenses.rentCents = 169_000;
        p.savings.liquidCents = 340_000;
      })
    );

    expect(three.known).toBeGreaterThan(one.known);
    expect(three.fraction).toBeGreaterThan(one.fraction);
    expect(three.fraction).toBeLessThanOrEqual(1);
  });

  it("reaches complete when every tracked field has been answered", () => {
    const progress = budgetProgress(
      edited((p) => {
        p.income.monthlyTakeHomeCents = 412_000;
        p.expenses.rentCents = 169_000;
        p.expenses.groceriesCents = 42_000;
        p.expenses.transportationCents = 13_780;
        p.expenses.utilitiesCents = 14_500;
        p.debt.minimumPaymentsCents = 26_000;
        p.debt.creditCardBalanceCents = 285_000;
        p.savings.liquidCents = 340_000;
      })
    );

    expect(progress.known).toBe(progress.total);
    expect(progress.fraction).toBe(1);
  });

  it("reports a value for every row, answered or not", () => {
    // The panel shows the example figure greyed out rather than a blank, so a
    // row must always carry a number to render.
    for (const row of budgetProgress(defaultProfile).rows) {
      expect(typeof row.cents).toBe("number");
      expect(Number.isFinite(row.cents)).toBe(true);
    }
  });

  it("cannot tell a real answer from one that matches the example", () => {
    // Documented blind spot: someone whose rent is exactly the demo's reads as
    // unanswered. Tracking provenance through the agent would fix it and cost
    // far more than being briefly wrong about one row.
    const progress = budgetProgress(
      edited((p) => {
        p.expenses.rentCents = defaultProfile.expenses.rentCents;
      })
    );

    expect(progress.rows.find((row) => row.id === "rent")?.known).toBe(false);
  });
});
