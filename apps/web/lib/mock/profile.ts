/**
 * Mock dataset for UI development.
 *
 * Every figure below is hand-derived from one consistent monthly model, so
 * the charts agree with each other and with the narrative copy. Money is in
 * integer cents to match the FastAPI contract, so swapping this for a real
 * /simulate response later is a type change, not a rewrite.
 *
 * The model, per month:
 *   cash += income - obligations - shocks
 *   if cash < 0 -> the deficit moves to revolving credit
 *   if credit would exceed the limit -> the remainder is unpaid (arrears)
 *
 * Credit is deliberately NOT treated as savings. Running out of cash and
 * running out of credit are two distinct failures with two distinct markers.
 */

export type RiskState = "resilient" | "stable" | "strained" | "critical";

export interface Person {
  name: string;
  age: number;
  occupation: string;
  city: string;
  state: string;
  household: string;
  incomeSources: number;
}

export interface DebtLine {
  id: string;
  name: string;
  balanceCents: number;
  minimumCents: number;
  aprBps: number;
  kind: "revolving" | "installment";
}

export const person: Person = {
  name: "Maya Restrepo",
  age: 27,
  occupation: "Dental hygienist",
  city: "Columbus",
  state: "OH",
  household: "1 adult, no dependents",
  incomeSources: 1,
};

/* ---------- monthly budget ---------- */

export const income = {
  monthlyTakeHomeCents: 468_000,
  payFrequency: "Biweekly",
  employer: "Single employer",
};

export const expenses = {
  rentCents: 165_000,
  utilitiesCents: 18_500,
  groceriesCents: 52_000,
  transportationCents: 34_000,
  insuranceCents: 21_000,
  otherEssentialCents: 9_500,
  subscriptionsCents: 6_800,
  discretionaryCents: 42_000,
};

export const debts: DebtLine[] = [
  {
    id: "card-a",
    name: "Chase Freedom",
    balanceCents: 189_000,
    minimumCents: 9_500,
    aprBps: 2499,
    kind: "revolving",
  },
  {
    id: "card-b",
    name: "Discover it",
    balanceCents: 95_000,
    minimumCents: 4_500,
    aprBps: 2199,
    kind: "revolving",
  },
  {
    id: "auto",
    name: "Auto loan",
    balanceCents: 820_000,
    minimumCents: 31_000,
    aprBps: 650,
    kind: "installment",
  },
  {
    id: "student",
    name: "Student loan",
    balanceCents: 1_840_000,
    minimumCents: 19_000,
    aprBps: 550,
    kind: "installment",
  },
];

export const credit = {
  balanceCents: 284_000, // card A + card B
  limitCents: 750_000,
  availableCents: 466_000,
};

export const savings = {
  liquidCents: 850_000,
};

/* ---------- derived baseline ---------- */

export const debtMinimumsCents = debts.reduce((sum, d) => sum + d.minimumCents, 0); // 64_000

/** Obligations that cannot be skipped without a real-world consequence. */
export const essentialCents =
  expenses.rentCents +
  expenses.utilitiesCents +
  expenses.groceriesCents +
  expenses.transportationCents +
  expenses.insuranceCents +
  expenses.otherEssentialCents +
  debtMinimumsCents; // 364_000

export const flexCents = expenses.subscriptionsCents + expenses.discretionaryCents; // 48_800

export const totalOutflowCents = essentialCents + flexCents; // 412_800

export const monthlyBufferCents = income.monthlyTakeHomeCents - totalOutflowCents; // 55_200

/** Months of essentials liquid savings alone would cover if income stopped today. */
export const baselineRunwayMonths = savings.liquidCents / essentialCents; // 2.335

/* ---------- the selected scenario ---------- */

export const assumptions = [
  { label: "Layoff begins", value: "Month 2" },
  { label: "Layoff duration", value: "5 months" },
  { label: "Severance", value: "$0" },
  { label: "Unemployment income", value: "$1,200 / mo" },
  { label: "Vehicle repair", value: "$2,400 in month 3" },
  { label: "Discretionary cut during crisis", value: "30% (automatic)" },
  { label: "Credit limit", value: "$7,500 (hard cap)" },
  { label: "Interest accrual", value: "Excluded from v1 model" },
];

export const CRISIS_INCOME_CENTS = 120_000;
/** During a crisis the model trims discretionary by 30%, not to zero. */
export const CRISIS_OUTFLOW_CENTS = essentialCents + Math.round(flexCents * 0.7); // 398_160 ≈ 398_200

export interface TimelineMonth {
  month: number;
  /** Liquid cash at month end. */
  cashCents: number;
  /** Revolving credit drawn at month end. */
  creditUsedCents: number;
  /** Obligations that could not be met by cash or credit. */
  arrearsCents: number;
  incomeCents: number;
  obligationsCents: number;
  utilization: number;
  phase: "normal" | "crisis" | "recovery";
  event?: string;
}

/**
 * Layoff months 2–6, vehicle repair in month 3.
 * Cash exhausted in month 4; credit limit reached in month 6.
 */
export const timeline: TimelineMonth[] = [
  { month: 0,  cashCents: 905_200,  creditUsedCents: 284_000, arrearsCents: 0,       incomeCents: 468_000, obligationsCents: 412_800, utilization: 0.379, phase: "normal" },
  { month: 1,  cashCents: 960_400,  creditUsedCents: 284_000, arrearsCents: 0,       incomeCents: 468_000, obligationsCents: 412_800, utilization: 0.379, phase: "normal" },
  { month: 2,  cashCents: 682_200,  creditUsedCents: 284_000, arrearsCents: 0,       incomeCents: 120_000, obligationsCents: 398_200, utilization: 0.379, phase: "crisis", event: "Layoff begins" },
  { month: 3,  cashCents: 164_000,  creditUsedCents: 284_000, arrearsCents: 0,       incomeCents: 120_000, obligationsCents: 638_200, utilization: 0.379, phase: "crisis", event: "Vehicle repair $2,400" },
  { month: 4,  cashCents: 0,        creditUsedCents: 398_200, arrearsCents: 0,       incomeCents: 120_000, obligationsCents: 398_200, utilization: 0.531, phase: "crisis", event: "Cash exhausted" },
  { month: 5,  cashCents: 0,        creditUsedCents: 676_400, arrearsCents: 0,       incomeCents: 120_000, obligationsCents: 398_200, utilization: 0.902, phase: "crisis" },
  { month: 6,  cashCents: 0,        creditUsedCents: 750_000, arrearsCents: 204_600, incomeCents: 120_000, obligationsCents: 398_200, utilization: 1.0,   phase: "crisis", event: "Credit exhausted — payment missed" },
  { month: 7,  cashCents: 0,        creditUsedCents: 750_000, arrearsCents: 149_400, incomeCents: 468_000, obligationsCents: 412_800, utilization: 1.0,   phase: "recovery", event: "Return to work" },
  { month: 8,  cashCents: 0,        creditUsedCents: 750_000, arrearsCents: 94_200,  incomeCents: 468_000, obligationsCents: 412_800, utilization: 1.0,   phase: "recovery" },
  { month: 9,  cashCents: 0,        creditUsedCents: 750_000, arrearsCents: 39_000,  incomeCents: 468_000, obligationsCents: 412_800, utilization: 1.0,   phase: "recovery" },
  { month: 10, cashCents: 0,        creditUsedCents: 733_800, arrearsCents: 0,       incomeCents: 468_000, obligationsCents: 412_800, utilization: 0.978, phase: "recovery", event: "Arrears cleared" },
  { month: 11, cashCents: 0,        creditUsedCents: 678_600, arrearsCents: 0,       incomeCents: 468_000, obligationsCents: 412_800, utilization: 0.905, phase: "recovery" },
];

/* ---------- verdict ---------- */

export const verdict = {
  headline:
    "You can absorb one major income shock — but not while a large expense lands on top of it.",
  riskState: "strained" as RiskState,
  shocksSurvivable: 1,
  /** Cash lasts months 0–3 in full, plus 59% of month 4. */
  monthsUntilCashOut: 4.6,
  /** Credit limit is reached 26% into month 6. */
  monthsUntilMissedPayment: 6.3,
  baselineRunwayMonths,
  primaryWeakness: "Loss of income",
  weaknessDetail:
    "All income comes from one employer, and $640/mo of it is already committed to debt minimums that do not pause during unemployment.",
  score: 54,
};

/* ---------- shock waterfall ---------- */

export interface WaterfallStep {
  label: string;
  amountCents: number;
  kind: "resource" | "drain" | "result";
  note?: string;
}

/**
 * Total capacity at the moment the layoff starts, and what consumes it
 * across the five crisis months. Sums exactly to the −$2,046 shortfall.
 */
export const waterfall: WaterfallStep[] = [
  { label: "Cash at shock start", amountCents: 960_400, kind: "resource", note: "After two normal months of saving" },
  { label: "Available credit", amountCents: 466_000, kind: "resource", note: "Borrowing capacity, not savings" },
  { label: "Unemployment income", amountCents: 600_000, kind: "resource", note: "$1,200 × 5 months" },
  { label: "Essential obligations", amountCents: -1_820_000, kind: "drain", note: "$3,640 × 5 months" },
  { label: "Reduced living costs", amountCents: -171_000, kind: "drain", note: "Discretionary already cut 30%" },
  { label: "Vehicle repair", amountCents: -240_000, kind: "drain", note: "Month 3" },
  { label: "Shortfall", amountCents: -204_600, kind: "result", note: "Obligations with no remaining way to pay" },
];

/* ---------- obligation stack ---------- */

export interface ObligationSlice {
  label: string;
  amountCents: number;
  tier: "required" | "semi-flexible" | "discretionary" | "surplus";
}

export const obligations: ObligationSlice[] = [
  { label: "Rent", amountCents: expenses.rentCents, tier: "required" },
  { label: "Debt minimums", amountCents: debtMinimumsCents, tier: "required" },
  { label: "Insurance", amountCents: expenses.insuranceCents, tier: "required" },
  { label: "Utilities", amountCents: expenses.utilitiesCents, tier: "required" },
  { label: "Other essential", amountCents: expenses.otherEssentialCents, tier: "required" },
  { label: "Groceries", amountCents: expenses.groceriesCents, tier: "semi-flexible" },
  { label: "Transportation", amountCents: expenses.transportationCents, tier: "semi-flexible" },
  { label: "Discretionary", amountCents: expenses.discretionaryCents, tier: "discretionary" },
  { label: "Subscriptions", amountCents: expenses.subscriptionsCents, tier: "discretionary" },
  { label: "Unallocated", amountCents: monthlyBufferCents, tier: "surplus" },
];

/* ---------- why it breaks ---------- */

export interface VulnerabilityDriver {
  label: string;
  detail: string;
  /** Share of the shortfall attributable to this driver, 0–1. */
  contribution: number;
  metric: string;
}

export const drivers: VulnerabilityDriver[] = [
  {
    label: "Single income source",
    detail: "One employer supplies 100% of household income, with no partner income or side earnings to fall back on.",
    contribution: 0.46,
    metric: "100% of income",
  },
  {
    label: "Locked debt minimums",
    detail: "$640/mo in minimums continues through unemployment. Over five crisis months that is $3,200 of unavoidable outflow.",
    contribution: 0.24,
    metric: "$640 / mo",
  },
  {
    label: "Thin emergency fund",
    detail: "Liquid savings cover 2.3 months of essentials. Absorbing this scenario without credit would take about 6.",
    contribution: 0.19,
    metric: "2.3 mo covered",
  },
  {
    label: "Housing share",
    detail: "Rent is 35% of take-home — high enough that the crisis budget cannot be trimmed far before hitting essentials.",
    contribution: 0.11,
    metric: "35% of income",
  },
];

/* ---------- how to improve ---------- */

export interface RecoveryAction {
  id: string;
  label: string;
  detail: string;
  monthsUntilMissedPayment: number | null; // null = survives the full horizon
  deltaLabel: string;
  effort: "low" | "medium" | "high";
}

export const recoveryActions: RecoveryAction[] = [
  {
    id: "current",
    label: "Current plan",
    detail: "No changes. Credit is exhausted six months in and a required payment is missed.",
    monthsUntilMissedPayment: 6.3,
    deltaLabel: "Breaks",
    effort: "low",
  },
  {
    id: "discretionary",
    label: "Cut discretionary to $200/mo",
    detail: "Frees $220/mo immediately. Over the crisis window that is $1,100 of additional capacity.",
    monthsUntilMissedPayment: 6.7,
    deltaLabel: "+0.4 mo",
    effort: "low",
  },
  {
    id: "card-a",
    label: "Pay off Chase Freedom",
    detail: "Clears $1,890 and frees the $95/mo minimum, which keeps running during unemployment.",
    monthsUntilMissedPayment: 6.9,
    deltaLabel: "+0.6 mo",
    effort: "medium",
  },
  {
    id: "save-more",
    label: "Save an extra $250/mo",
    detail: "Two months of extra saving before the shock lands adds $500 to the starting buffer.",
    monthsUntilMissedPayment: 7.0,
    deltaLabel: "+0.7 mo",
    effort: "medium",
  },
  {
    id: "fund",
    label: "Emergency fund to $11,000",
    detail: "Adds $2,500 — slightly more than the $2,046 shortfall. This scenario becomes survivable outright.",
    monthsUntilMissedPayment: null,
    deltaLabel: "Clears the gap",
    effort: "high",
  },
  {
    id: "combined",
    label: "Combined plan",
    detail: "Discretionary cut, Card A paid off, and the fund raised together. Credit never exceeds 61%.",
    monthsUntilMissedPayment: null,
    deltaLabel: "Wide margin",
    effort: "high",
  },
];

/* ---------- scenario comparison ---------- */

export interface ScenarioSeries {
  id: string;
  label: string;
  breaksAtMonth: number | null;
  /** Cash at each month end; once cash is gone the series pins to zero. */
  cash: number[];
}

export const scenarioComparison: ScenarioSeries[] = [
  {
    id: "baseline",
    label: "No shocks",
    breaksAtMonth: null,
    cash: [905_200, 960_400, 1_015_600, 1_070_800, 1_126_000, 1_181_200, 1_236_400, 1_291_600, 1_346_800, 1_402_000, 1_457_200, 1_512_400],
  },
  {
    id: "repair",
    label: "Vehicle repair only",
    breaksAtMonth: null,
    cash: [905_200, 960_400, 1_015_600, 830_800, 886_000, 941_200, 996_400, 1_051_600, 1_106_800, 1_162_000, 1_217_200, 1_272_400],
  },
  {
    id: "layoff",
    label: "Layoff only",
    breaksAtMonth: null,
    cash: [905_200, 960_400, 682_200, 404_000, 125_800, 0, 0, 0, 0, 0, 0, 0],
  },
  {
    id: "compound",
    label: "Layoff + repair",
    breaksAtMonth: 6,
    cash: [905_200, 960_400, 682_200, 164_000, 0, 0, 0, 0, 0, 0, 0, 0],
  },
];

/* ---------- compound shock matrix ---------- */

export const shockNames = ["Layoff", "Vehicle repair", "Rent +$250", "Medical $1,800"];

/**
 * Months until a required payment is missed when two shocks land together.
 * null means the pair is survivable across the 12-month horizon.
 */
export const compoundMatrix: (number | null)[][] = [
  [null, 6.3, 6.6, 6.5],
  [6.3, null, null, null],
  [6.6, null, null, null],
  [6.5, null, null, null],
];

/* ---------- shock library ---------- */

export interface ShockOption {
  id: string;
  label: string;
  defaultCost: string;
  category: "income" | "expense" | "recurring";
  /** Share of US adults reporting this class of expense, Fed SHED 2025. */
  prevalence?: string;
  active: boolean;
}

export const shockLibrary: ShockOption[] = [
  { id: "layoff", label: "Layoff", defaultCost: "5 mo · $1,200 UI", category: "income", active: true },
  { id: "vehicle", label: "Vehicle repair", defaultCost: "$2,400", category: "expense", prevalence: "Most common", active: true },
  { id: "hours", label: "Reduced hours", defaultCost: "−30% income", category: "income", active: false },
  { id: "home", label: "Home or appliance repair", defaultCost: "$1,600", category: "expense", prevalence: "2nd most common", active: false },
  { id: "medical", label: "Medical expense", defaultCost: "$1,800", category: "expense", prevalence: "3rd most common", active: false },
  { id: "rent", label: "Rent increase", defaultCost: "+$250 / mo", category: "recurring", active: false },
  { id: "deductible", label: "Insurance deductible", defaultCost: "$1,000", category: "expense", active: false },
  { id: "grocery", label: "Grocery inflation", defaultCost: "+8% / mo", category: "recurring", active: false },
  { id: "utility", label: "Utility increase", defaultCost: "+$60 / mo", category: "recurring", active: false },
  { id: "family", label: "Family emergency", defaultCost: "$1,500", category: "expense", active: false },
  { id: "disaster", label: "Natural disaster", defaultCost: "$3,000", category: "expense", active: false },
  { id: "custom", label: "Custom event", defaultCost: "Configure", category: "expense", active: false },
];

/* ---------- receipt ---------- */

export const receipt = {
  formulaVersion: "sim-engine 0.4.0",
  schemaVersion: 1,
  runAt: "2026-08-05T14:22:31Z",
  seed: "deterministic — no sampling",
  sources: [
    "User-entered financial profile",
    "Fed SHED 2025 — unexpected expense prevalence",
    "BLS Consumer Expenditure Survey — category benchmarks",
  ],
};
