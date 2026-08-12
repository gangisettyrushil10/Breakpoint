import type {
  FinancialProfile,
  ScenarioInput,
  SimulateResponse,
} from "./types";
import type { RiskState, TimelineMonth, ObligationSlice, RecoveryAction } from "@/lib/mock/profile";

/** Demo profile aligned with the Maya Restrepo mock budget (API-shaped). */
export const defaultProfile: FinancialProfile = {
  schemaVersion: 1,
  currency: "USD",
  location: { city: "Columbus", state: "OH", postalCode: "43215" },
  household: { dependents: 0, jobStability: "stable" },
  income: { monthlyTakeHomeCents: 468_000, payFrequency: "biweekly" },
  expenses: {
    rentCents: 165_000,
    utilitiesCents: 18_500,
    groceriesCents: 52_000,
    transportationCents: 34_000,
    insuranceCents: 21_000,
    subscriptionsCents: 6_800,
    discretionaryCents: 42_000,
    otherEssentialCents: 9_500,
  },
  debt: {
    minimumPaymentsCents: 64_000,
    creditCardBalanceCents: 284_000,
    availableCreditCents: 466_000,
    creditAprBps: 2499,
  },
  savings: { liquidCents: 850_000 },
};

export const SIM_MONTHS = 12;

export type ShockId =
  | "layoff"
  | "vehicle"
  | "medical"
  | "rent"
  | "home"
  | "deductible"
  | "family"
  | "disaster"
  | "custom";

/**
 * The one definition of what each shock costs and when it lands.
 *
 * Everything downstream — the scenarios POSTed to `/simulate`, the catalog
 * labels, the assumptions table, the timeline event markers — reads from here.
 * They used to carry their own copies of these figures, which was invisible
 * while every user got the same demo budget and would have become a page full
 * of confidently wrong numbers the moment anyone entered their own.
 *
 * The backend owns the *engine* defaults; these are the UI's choices about
 * which shocks to offer and how to parameterise them, sent explicitly on every
 * request so the two can never silently disagree.
 */
export const SHOCK_PARAMS = {
  layoff: {
    startMonth: 2,
    maxDurationMonths: 5,
    replacementIncomeCents: 120_000,
  },
  vehicle: { monthIndex: 3, costCents: 240_000 },
  medical: { monthIndex: 3, costCents: 180_000 },
  rent: { startMonth: 1, increaseCents: 25_000 },
  home: { monthIndex: 2, costCents: 160_000, name: "home_repair" },
  deductible: { monthIndex: 1, costCents: 100_000, name: "insurance_deductible" },
  family: { monthIndex: 2, costCents: 150_000, name: "family_emergency" },
  disaster: { monthIndex: 1, costCents: 300_000, name: "natural_disaster" },
  custom: { monthIndex: 0, costCents: 50_000, name: "custom_event" },
} as const;

/** How long a layoff runs given the horizon — the engine can't outlast it. */
export function layoffDuration(months: number): number {
  return Math.min(
    SHOCK_PARAMS.layoff.maxDurationMonths,
    Math.max(1, months - SHOCK_PARAMS.layoff.startMonth)
  );
}

function dollars(cents: number): string {
  return `$${(cents / 100).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

export interface ShockCatalogItem {
  id: ShockId;
  label: string;
  defaultCost: string;
  category: "income" | "expense" | "recurring";
  prevalence?: string;
  /** Only shocks with a builder are sent to the API. */
  supported: boolean;
}

export const shockCatalog: ShockCatalogItem[] = [
  {
    id: "layoff",
    label: "Layoff",
    defaultCost: `${SHOCK_PARAMS.layoff.maxDurationMonths} mo · ${dollars(
      SHOCK_PARAMS.layoff.replacementIncomeCents
    )} UI`,
    category: "income",
    supported: true,
  },
  {
    id: "vehicle",
    label: "Vehicle repair",
    defaultCost: dollars(SHOCK_PARAMS.vehicle.costCents),
    category: "expense",
    prevalence: "Most common",
    supported: true,
  },
  {
    id: "home",
    label: "Home or appliance repair",
    defaultCost: dollars(SHOCK_PARAMS.home.costCents),
    category: "expense",
    prevalence: "2nd most common",
    supported: true,
  },
  {
    id: "medical",
    label: "Medical expense",
    defaultCost: dollars(SHOCK_PARAMS.medical.costCents),
    category: "expense",
    prevalence: "3rd most common",
    supported: true,
  },
  {
    id: "rent",
    label: "Rent increase",
    defaultCost: `+${dollars(SHOCK_PARAMS.rent.increaseCents)} / mo`,
    category: "recurring",
    supported: true,
  },
  {
    id: "deductible",
    label: "Insurance deductible",
    defaultCost: dollars(SHOCK_PARAMS.deductible.costCents),
    category: "expense",
    supported: true,
  },
  {
    id: "family",
    label: "Family emergency",
    defaultCost: dollars(SHOCK_PARAMS.family.costCents),
    category: "expense",
    supported: true,
  },
  {
    id: "disaster",
    label: "Natural disaster",
    defaultCost: dollars(SHOCK_PARAMS.disaster.costCents),
    category: "expense",
    supported: true,
  },
  {
    id: "custom",
    label: "Custom event",
    defaultCost: dollars(SHOCK_PARAMS.custom.costCents),
    category: "expense",
    supported: true,
  },
];

export const DEFAULT_ACTIVE_SHOCKS: ShockId[] = ["layoff", "vehicle"];

/** Map UI shock toggles → API scenario objects. */
export function scenariosFromShockIds(ids: ShockId[], months: number): ScenarioInput[] {
  const scenarios: ScenarioInput[] = [];

  for (const id of ids) {
    switch (id) {
      case "layoff":
        scenarios.push({
          type: "layoff",
          startMonth: SHOCK_PARAMS.layoff.startMonth,
          durationMonths: layoffDuration(months),
          replacementIncomeCents: SHOCK_PARAMS.layoff.replacementIncomeCents,
        });
        break;
      case "vehicle":
        scenarios.push({ type: "car_repair", ...SHOCK_PARAMS.vehicle });
        break;
      case "medical":
        scenarios.push({ type: "medical_bill", ...SHOCK_PARAMS.medical });
        break;
      case "rent":
        scenarios.push({
          type: "rent_hike",
          startMonth: SHOCK_PARAMS.rent.startMonth,
          durationMonths: Math.max(1, months - SHOCK_PARAMS.rent.startMonth),
          increaseCents: SHOCK_PARAMS.rent.increaseCents,
        });
        break;
      case "home":
        scenarios.push({ type: "custom_shock", ...SHOCK_PARAMS.home });
        break;
      case "deductible":
        scenarios.push({ type: "custom_shock", ...SHOCK_PARAMS.deductible });
        break;
      case "family":
        scenarios.push({ type: "custom_shock", ...SHOCK_PARAMS.family });
        break;
      case "disaster":
        scenarios.push({ type: "custom_shock", ...SHOCK_PARAMS.disaster });
        break;
      case "custom":
        scenarios.push({ type: "custom_shock", ...SHOCK_PARAMS.custom });
        break;
    }
  }

  return scenarios.filter((s) => {
    if ("monthIndex" in s) return s.monthIndex < months;
    return s.startMonth < months;
  });
}

export function riskStateFromScore(score: number): RiskState {
  if (score >= 85) return "resilient";
  if (score >= 70) return "stable";
  if (score >= 50) return "strained";
  return "critical";
}

export function monthsUntilCashOut(
  result: SimulateResponse,
  creditLimitCents: number
): number | null {
  void creditLimitCents;
  for (const month of result.simulation.months) {
    if (month.state.cashCents <= 0) return month.monthIndex;
  }
  return null;
}

export function monthsUntilCreditExhausted(
  result: SimulateResponse,
  availableCreditCents: number,
  startingBalanceCents: number
): number | null {
  const limit = startingBalanceCents + availableCreditCents;
  for (const month of result.simulation.months) {
    if (month.state.creditCardBalanceCents >= limit) return month.monthIndex;
  }
  if (result.breakingPoint.triggered && result.breakingPoint.monthIndex != null) {
    return result.breakingPoint.monthIndex;
  }
  return null;
}

export function buildTimeline(
  result: SimulateResponse,
  profile: FinancialProfile,
  activeIds: ShockId[]
): TimelineMonth[] {
  const creditLimit =
    profile.debt.creditCardBalanceCents + profile.debt.availableCreditCents;
  const layoffOn = activeIds.includes("layoff");
  const vehicleOn = activeIds.includes("vehicle");

  // Derived from the same constants that built the scenarios we POSTed, so the
  // markers on the chart describe the run the engine actually did.
  const months = result.simulation.months.length;
  const layoffStart = SHOCK_PARAMS.layoff.startMonth;
  const layoffEnd = layoffStart + layoffDuration(months) - 1;

  return result.simulation.months.map((m) => {
    const creditUsed = m.state.creditCardBalanceCents;
    const utilization = creditLimit > 0 ? Math.min(1, creditUsed / creditLimit) : 0;
    const arrears = Math.max(0, creditUsed - creditLimit);

    const inLayoff = layoffOn && m.monthIndex >= layoffStart && m.monthIndex <= layoffEnd;

    let phase: TimelineMonth["phase"] = "normal";
    if (inLayoff) phase = "crisis";
    else if (layoffOn && m.monthIndex > layoffEnd) phase = "recovery";

    let event: string | undefined;
    if (layoffOn && m.monthIndex === layoffStart) event = "Layoff begins";
    if (vehicleOn && m.monthIndex === SHOCK_PARAMS.vehicle.monthIndex) {
      event = `Vehicle repair ${dollars(SHOCK_PARAMS.vehicle.costCents)}`;
    }
    if (m.state.cashCents <= 0 && m.monthIndex > 0) {
      const prev = result.simulation.months[m.monthIndex - 1];
      if (prev && prev.state.cashCents > 0) event = "Cash exhausted";
    }
    if (
      result.breakingPoint.triggered &&
      result.breakingPoint.monthIndex === m.monthIndex
    ) {
      event = "Credit exhausted — payment missed";
    }

    const incomeCents = inLayoff
      ? SHOCK_PARAMS.layoff.replacementIncomeCents
      : profile.income.monthlyTakeHomeCents;

    return {
      month: m.monthIndex,
      cashCents: m.state.cashCents,
      creditUsedCents: creditUsed,
      arrearsCents: arrears,
      incomeCents,
      obligationsCents: result.baseline.totalExpensesCents,
      utilization,
      phase,
      event,
    };
  });
}

export function buildObligations(
  profile: FinancialProfile,
  bufferCents: number
): ObligationSlice[] {
  const e = profile.expenses;
  return [
    { label: "Rent", amountCents: e.rentCents, tier: "required" },
    {
      label: "Debt minimums",
      amountCents: profile.debt.minimumPaymentsCents,
      tier: "required",
    },
    { label: "Insurance", amountCents: e.insuranceCents, tier: "required" },
    { label: "Utilities", amountCents: e.utilitiesCents, tier: "required" },
    {
      label: "Other essential",
      amountCents: e.otherEssentialCents,
      tier: "required",
    },
    { label: "Groceries", amountCents: e.groceriesCents, tier: "semi-flexible" },
    {
      label: "Transportation",
      amountCents: e.transportationCents,
      tier: "semi-flexible",
    },
    {
      label: "Discretionary",
      amountCents: e.discretionaryCents,
      tier: "discretionary",
    },
    {
      label: "Subscriptions",
      amountCents: e.subscriptionsCents,
      tier: "discretionary",
    },
    {
      label: "Unallocated",
      amountCents: Math.max(0, bufferCents),
      tier: "surplus",
    },
  ];
}

export function buildVerdict(
  result: SimulateResponse,
  profile: FinancialProfile,
  activeIds: ShockId[]
) {
  const cashOut = monthsUntilCashOut(result, profile.debt.availableCreditCents);
  const missPayment = monthsUntilCreditExhausted(
    result,
    profile.debt.availableCreditCents,
    profile.debt.creditCardBalanceCents
  );
  const runway = result.baseline.runwayMonths ?? 0;
  const score = result.resilience.score;
  const riskState = riskStateFromScore(score);

  const rentShare = eRentShare(profile);
  const primaryWeakness =
    runway < 3
      ? "Thin emergency fund"
      : rentShare > 0.3
        ? "Housing share"
        : "Fixed obligations";

  const weaknessDetail =
    primaryWeakness === "Thin emergency fund"
      ? `Liquid savings cover about ${runway.toFixed(1)} months of essentials. Stacked shocks burn that buffer quickly.`
      : primaryWeakness === "Housing share"
        ? `Rent is ${(rentShare * 100).toFixed(0)}% of take-home — hard to trim under stress.`
        : `Debt minimums of $${(profile.debt.minimumPaymentsCents / 100).toFixed(0)}/mo keep running even when income drops.`;

  const headline = result.breakingPoint.triggered
    ? "This budget breaks when the selected shocks stack — credit is not a safety net forever."
    : activeIds.length === 0
      ? "In a normal month this budget holds. Add shocks to find the breaking point."
      : "Under the selected shocks, cash and credit absorb the hit within the simulated window.";

  return {
    headline,
    riskState,
    shocksSurvivable: result.breakingPoint.triggered ? Math.max(0, activeIds.length - 1) : activeIds.length,
    monthsUntilCashOut: cashOut ?? result.simulation.months.length,
    monthsUntilMissedPayment: missPayment ?? result.simulation.months.length,
    baselineRunwayMonths: runway,
    primaryWeakness,
    weaknessDetail,
    score,
  };
}

function eRentShare(profile: FinancialProfile) {
  return profile.expenses.rentCents / profile.income.monthlyTakeHomeCents;
}

export function buildRecoveryActions(result: SimulateResponse): RecoveryAction[] {
  const plan = result.preventionPlan;
  const breakAt = result.breakingPoint.monthIndex;
  const current: RecoveryAction = {
    id: "current",
    label: "Current plan",
    detail: result.breakingPoint.triggered
      ? `Severe risk triggers around month ${breakAt}. Credit overage ≈ $${((result.breakingPoint.overageCents ?? 0) / 100).toFixed(0)}.`
      : "No severe-risk trigger in this run. Keep building buffer.",
    monthsUntilMissedPayment: result.breakingPoint.triggered ? (breakAt ?? 0) : null,
    deltaLabel: result.breakingPoint.triggered ? "Breaks" : "Holds",
    effort: "low",
  };

  if (!plan || plan.alreadyOverCreditLimit) {
    return [current];
  }

  const actions: RecoveryAction[] = [current];

  if (plan.monthlyCutCentsNeeded != null) {
    actions.push({
      id: "cut",
      label: `Cut spending by $${(plan.monthlyCutCentsNeeded / 100).toFixed(0)}/mo`,
      detail: plan.monthlyCutFeasible
        ? `Within cuttable subscriptions + discretionary ($${plan.cuttableMonthlyCents / 100}/mo available).`
        : `Needed cut exceeds cuttable flexible spend ($${plan.cuttableMonthlyCents / 100}/mo).`,
      monthsUntilMissedPayment: plan.monthlyCutFeasible ? null : breakAt,
      deltaLabel: plan.monthlyCutFeasible ? "Clears gap" : "Not enough flex",
      effort: "medium",
    });
  }

  if (plan.extraSavingsCentsNeeded != null) {
    actions.push({
      id: "save",
      label: `Raise emergency fund by $${(plan.extraSavingsCentsNeeded / 100).toFixed(0)}`,
      detail: "Extra liquid savings equal to the credit overage that triggered severe risk.",
      monthsUntilMissedPayment: null,
      deltaLabel: "Clears the gap",
      effort: "high",
    });
  }

  return actions;
}

export function buildAssumptions(
  activeIds: ShockId[],
  months: number
): { label: string; value: string }[] {
  const rows: { label: string; value: string }[] = [
    { label: "Simulation horizon", value: `${months} months` },
    { label: "Interest accrual", value: "Excluded from v1 model" },
    { label: "Credit limit", value: "Starting balance + available credit" },
  ];

  // Every figure below is read from SHOCK_PARAMS — the same constants that
  // built the scenarios sent to /simulate. This table is the page's "show your
  // work" section, so a stale literal here would be a lie about the run.
  if (activeIds.includes("layoff")) {
    rows.unshift(
      { label: "Layoff begins", value: `Month ${SHOCK_PARAMS.layoff.startMonth}` },
      { label: "Layoff duration", value: `${layoffDuration(months)} months` },
      {
        label: "Unemployment income",
        value: `${dollars(SHOCK_PARAMS.layoff.replacementIncomeCents)} / mo`,
      }
    );
  }
  if (activeIds.includes("vehicle")) {
    rows.push({
      label: "Vehicle repair",
      value: `${dollars(SHOCK_PARAMS.vehicle.costCents)} in month ${SHOCK_PARAMS.vehicle.monthIndex}`,
    });
  }
  if (activeIds.includes("medical")) {
    rows.push({
      label: "Medical bill",
      value: `${dollars(SHOCK_PARAMS.medical.costCents)} in month ${SHOCK_PARAMS.medical.monthIndex}`,
    });
  }
  if (activeIds.includes("rent")) {
    rows.push({
      label: "Rent hike",
      value: `+${dollars(SHOCK_PARAMS.rent.increaseCents)} / mo from month ${SHOCK_PARAMS.rent.startMonth}`,
    });
  }

  return rows;
}

export function buildDrivers(profile: FinancialProfile, result: SimulateResponse) {
  const runway = result.baseline.runwayMonths ?? 0;
  const rentShare = eRentShare(profile);
  const debtShare =
    profile.debt.minimumPaymentsCents / profile.income.monthlyTakeHomeCents;

  return [
    {
      label: "Single income source",
      detail: "One take-home stream funds the whole household in this profile.",
      contribution: 0.4,
      metric: "100% of income",
    },
    {
      label: "Locked debt minimums",
      detail: `$${(profile.debt.minimumPaymentsCents / 100).toFixed(0)}/mo in minimums continues through income shocks.`,
      contribution: Math.min(0.35, debtShare),
      metric: `$${Math.round(profile.debt.minimumPaymentsCents / 100)} / mo`,
    },
    {
      label: "Emergency runway",
      detail: `Liquid savings cover about ${runway.toFixed(1)} months of essentials.`,
      contribution: runway < 3 ? 0.25 : 0.12,
      metric: `${runway.toFixed(1)} mo covered`,
    },
    {
      label: "Housing share",
      detail: `Rent is ${(rentShare * 100).toFixed(0)}% of take-home.`,
      contribution: Math.min(0.2, rentShare),
      metric: `${(rentShare * 100).toFixed(0)}% of income`,
    },
  ];
}
