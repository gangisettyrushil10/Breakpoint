/** TypeScript mirrors of the FastAPI /simulate contract. Money is integer cents. */

export type PayFrequency = "weekly" | "biweekly" | "semimonthly" | "monthly";
export type JobStability = "stable" | "contract" | "unstable";

export interface FinancialProfile {
  schemaVersion: number;
  currency: string;
  location: { city: string; state: string; postalCode: string };
  household: { dependents: number; jobStability: JobStability };
  income: { monthlyTakeHomeCents: number; payFrequency: PayFrequency };
  expenses: {
    rentCents: number;
    utilitiesCents: number;
    groceriesCents: number;
    transportationCents: number;
    insuranceCents: number;
    subscriptionsCents: number;
    discretionaryCents: number;
    otherEssentialCents: number;
  };
  debt: {
    minimumPaymentsCents: number;
    creditCardBalanceCents: number;
    availableCreditCents: number;
    creditAprBps: number;
  };
  savings: { liquidCents: number };
}

export type ScenarioInput =
  | { type: "car_repair"; monthIndex: number; costCents?: number }
  | { type: "medical_bill"; monthIndex: number; costCents?: number }
  | {
      type: "rent_hike";
      startMonth: number;
      durationMonths: number;
      increaseCents: number;
    }
  | {
      type: "layoff";
      startMonth: number;
      durationMonths: number;
      replacementIncomeCents?: number;
    }
  | { type: "custom_shock"; monthIndex: number; name: string; costCents: number };

export interface SimulateRequest {
  profile: FinancialProfile;
  months: number;
  scenarios: ScenarioInput[];
}

export interface BaselineResult {
  fixedExpensesCents: number;
  essentialExpensesCents: number;
  totalExpensesCents: number;
  monthlyBufferCents: number;
  runwayMonths: number | null;
}

export interface ResilienceScore {
  score: number;
  runwaySubscore: number;
  bufferSubscore: number;
  creditSubscore: number;
}

export interface MonthState {
  cashCents: number;
  creditCardBalanceCents: number;
}

export interface MonthResult {
  monthIndex: number;
  state: MonthState;
}

export interface SimulationResult {
  months: MonthResult[];
}

export interface BreakingPoint {
  triggered: boolean;
  monthIndex: number | null;
  shockCombination: string[];
  overageCents: number | null;
}

export interface PreventionPlan {
  alreadyOverCreditLimit: boolean;
  extraSavingsCentsNeeded: number | null;
  monthlyCutCentsNeeded: number | null;
  cuttableMonthlyCents: number;
  monthlyCutFeasible: boolean | null;
}

export interface SimulateResponse {
  baseline: BaselineResult;
  resilience: ResilienceScore;
  simulation: SimulationResult;
  breakingPoint: BreakingPoint;
  preventionPlan: PreventionPlan | null;
}

/* ---------------------------------------------------------------------------
 * Agent chat — mirrors the FastAPI /agent/chat contract.
 * The client owns the conversation: send the full history and the working
 * profile every turn, get both back.
 * ------------------------------------------------------------------------ */

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

/** What the agent actually ran, so the UI can show its work. */
export interface ToolCallRecord {
  name: string;
  arguments: Record<string, unknown>;
  ok: boolean;
}

/** Why a reply was blocked, regenerated, or withheld — if it was. */
export interface GuardrailReport {
  blocked: boolean;
  regenerated: boolean;
  /** Figures the model stated that the tool output couldn't account for. */
  unsupported: string[];
  reasons: string[];
  /**
   * @deprecated Numbers are no longer rewritten in place — an ungrounded reply
   * is regenerated or withheld. Always false; kept for wire compatibility.
   */
  amended: boolean;
}

export interface ChatRequest {
  messages: ChatMessage[];
  profile: FinancialProfile;
  months: number;
}

export interface ChatResponse {
  messages: ChatMessage[];
  reply: string;
  /** Echoed back, possibly edited by the agent's `patch_profile` tool. */
  profile: FinancialProfile;
  /**
   * The run describing the user's actual situation — the unstressed one where
   * the turn simulated several. This is what the dashboard should render.
   */
  simulateResult: SimulateResponse | null;
  /** Every simulation this turn, in call order (a turn may compare scenarios). */
  simulateRuns: SimulateResponse[];
  toolCalls: ToolCallRecord[];
  guardrail: GuardrailReport;
  stopReason: string | null;
  /** Tokens across every model call this turn — what it actually cost. */
  totalTokens: number;
  /** How many times the model was called. Two is the normal shape. */
  modelCalls: number;
}

/* ---------------------------------------------------------------------------
 * Streaming — mirrors `services/api/app/agent/events.py`.
 *
 * The whole contract in one line: **`done` replaces everything.** Every other
 * event is progressive disclosure, so streamed text can never disagree with the
 * final reply — it is discarded the moment `done` lands.
 * ------------------------------------------------------------------------ */

export type AgentEvent =
  | { type: "start"; months: number }
  | {
      type: "tool_call";
      name: string;
      arguments: Record<string, unknown>;
      ok: boolean;
    }
  /**
   * A hypothetical was priced. Nothing changed — this must not be handled like
   * a `profile` event, or the app would show a budget the user never agreed to.
   */
  | {
      type: "what_if";
      scoreBefore: number;
      scoreAfter: number;
      changed: string[];
    }
  | {
      type: "simulate_run";
      index: number;
      hasScenarios: boolean;
      result: SimulateResponse;
    }
  | { type: "profile"; profile: FinancialProfile }
  | { type: "sentence"; text: string }
  /** Clear the bubble — never append a correction to retracted text. */
  | { type: "retract"; reason: string }
  | { type: "notice"; kind: "regenerating" | "withheld" | "blocked"; detail: string }
  | { type: "done"; response: ChatResponse }
  | { type: "error"; detail: string };
