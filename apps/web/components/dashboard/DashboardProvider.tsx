"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useProfile } from "@/components/ProfileProvider";
import { simulate } from "@/lib/api/client";
import type { FinancialProfile, SimulateResponse } from "@/lib/api/types";
import {
  DEFAULT_ACTIVE_SHOCKS,
  SHOCK_PARAMS,
  layoffDuration,
  buildAssumptions,
  buildDrivers,
  buildObligations,
  buildRecoveryActions,
  buildTimeline,
  buildVerdict,
  scenariosFromShockIds,
  shockCatalog,
  type ShockId,
} from "@/lib/api/mappers";
import type {
  ObligationSlice,
  RecoveryAction,
  ScenarioSeries,
  TimelineMonth,
  WaterfallStep,
} from "@/lib/mock/profile";
import { person as mockPerson } from "@/lib/mock/profile";

export interface DashboardPerson {
  name: string;
  age: number;
  occupation: string;
  city: string;
  state: string;
  household: string;
}

interface DashboardContextValue {
  profile: FinancialProfile;
  person: DashboardPerson;
  months: number;
  activeShocks: ShockId[];
  setActiveShocks: (ids: ShockId[]) => void;
  toggleShock: (id: ShockId) => void;
  result: SimulateResponse | null;
  loading: boolean;
  error: string | null;
  rerun: () => void;
  verdict: ReturnType<typeof buildVerdict> | null;
  timeline: TimelineMonth[];
  obligations: ObligationSlice[];
  recoveryActions: RecoveryAction[];
  assumptions: { label: string; value: string }[];
  drivers: ReturnType<typeof buildDrivers>;
  waterfall: WaterfallStep[];
  scenarioComparison: ScenarioSeries[];
  compoundShockNames: string[];
  compoundMatrix: (number | null)[][];
  creditLimitCents: number;
  comparisonLoading: boolean;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

const COMPOUND_SHOCK_NAMES = [
  "Layoff",
  "Vehicle repair",
  "Rent +$250",
  "Medical $1,800",
];
const COMPOUND_SHOCK_IDS: ShockId[][] = [
  ["layoff"],
  ["vehicle"],
  ["rent"],
  ["medical"],
];

/**
 * The comparison matrix costs 16 `/simulate` calls (4 baselines + 12 pairwise).
 * That was harmless while the profile was a frozen constant; now that the agent
 * can edit it mid-conversation, a burst of edits would fire a burst of storms.
 * The primary run stays eager — it is what the page is *about* — and only this
 * expensive tail waits for the profile to settle.
 */
const COMPARISON_DEBOUNCE_MS = 500;

/** An aborted run is a superseded run, not a failure worth showing the user. */
function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export function useDashboard() {
  const ctx = useContext(DashboardContext);
  if (!ctx) throw new Error("useDashboard must be used within DashboardProvider");
  return ctx;
}

export function DashboardProvider({ children }: { children: ReactNode }) {
  // The profile now lives above the router, so the agent's edits on /chat and
  // the numbers on this page are the same object.
  const { profile, months, hydrated } = useProfile();
  const [activeShocks, setActiveShocks] = useState<ShockId[]>(DEFAULT_ACTIVE_SHOCKS);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scenarioComparison, setScenarioComparison] = useState<ScenarioSeries[]>([]);
  const [compoundMatrix, setCompoundMatrix] = useState<(number | null)[][]>([
    [null, null, null, null],
    [null, null, null, null],
    [null, null, null, null],
    [null, null, null, null],
  ]);
  const [comparisonLoading, setComparisonLoading] = useState(false);

  const person: DashboardPerson = {
    ...mockPerson,
    city: profile.location.city,
    state: profile.location.state,
  };

  const creditLimitCents =
    profile.debt.creditCardBalanceCents + profile.debt.availableCreditCents;

  const runPrimary = useCallback(
    async (ids: ShockId[], signal?: AbortSignal) => {
      setLoading(true);
      setError(null);
      try {
        const data = await simulate(
          {
            profile,
            months,
            scenarios: scenariosFromShockIds(ids, months),
          },
          { signal }
        );
        setResult(data);
      } catch (err) {
        // A superseded run must not clear the result — the newer run owns it.
        if (isAbort(err)) return;
        setError(err instanceof Error ? err.message : "Failed to run simulation");
        setResult(null);
      } finally {
        if (!signal?.aborted) setLoading(false);
      }
    },
    [profile, months]
  );

  const runComparisons = useCallback(
    async (signal?: AbortSignal) => {
    setComparisonLoading(true);
    try {
      const variants: { id: string; label: string; ids: ShockId[] }[] = [
        { id: "baseline", label: "No shocks", ids: [] },
        { id: "repair", label: "Vehicle repair only", ids: ["vehicle"] },
        { id: "layoff", label: "Layoff only", ids: ["layoff"] },
        { id: "compound", label: "Layoff + repair", ids: ["layoff", "vehicle"] },
      ];

      const series = await Promise.all(
        variants.map(async (v) => {
          const data = await simulate(
            {
              profile,
              months,
              scenarios: scenariosFromShockIds(v.ids, months),
            },
            { signal }
          );
          return {
            id: v.id,
            label: v.label,
            breaksAtMonth: data.breakingPoint.triggered
              ? data.breakingPoint.monthIndex
              : null,
            cash: data.simulation.months.map((m) => m.state.cashCents),
          };
        })
      );
      setScenarioComparison(series);

      const n = COMPOUND_SHOCK_IDS.length;
      const matrix: (number | null)[][] = Array.from({ length: n }, () =>
        Array.from({ length: n }, () => null)
      );
      const pairJobs: Promise<void>[] = [];
      for (let i = 0; i < n; i++) {
        for (let j = 0; j < n; j++) {
          if (i === j) continue;
          const ids = [
            ...new Set([...COMPOUND_SHOCK_IDS[i], ...COMPOUND_SHOCK_IDS[j]]),
          ];
          pairJobs.push(
            (async () => {
              const data = await simulate(
                {
                  profile,
                  months,
                  scenarios: scenariosFromShockIds(ids, months),
                },
                { signal }
              );
              matrix[i][j] = data.breakingPoint.triggered
                ? data.breakingPoint.monthIndex
                : null;
            })()
          );
        }
      }
      await Promise.all(pairJobs);
      setCompoundMatrix(matrix.map((row) => [...row]));
    } catch (err) {
      if (isAbort(err)) return;
      setScenarioComparison([]);
    } finally {
      if (!signal?.aborted) setComparisonLoading(false);
    }
    },
    [profile, months]
  );

  // Eager: this is the run the page is about. Aborting the previous one keeps a
  // slow earlier request from landing on top of a newer profile.
  //
  // `runPrimary` flips `loading` before awaiting the network — fetching on mount
  // is the external-system sync this rule is meant to permit, but it only sees
  // the synchronous setState.
  useEffect(() => {
    if (!hydrated) return;
    const controller = new AbortController();
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void runPrimary(activeShocks, controller.signal);
    return () => controller.abort();
  }, [hydrated, activeShocks, runPrimary]);

  // Debounced: 16 requests per run, so let the profile settle first.
  useEffect(() => {
    if (!hydrated) return;
    const controller = new AbortController();
    const timer = setTimeout(
      () => void runComparisons(controller.signal),
      COMPARISON_DEBOUNCE_MS
    );
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [hydrated, runComparisons]);

  const toggleShock = useCallback((id: ShockId) => {
    setActiveShocks((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }, []);

  const verdict = useMemo(
    () => (result ? buildVerdict(result, profile, activeShocks) : null),
    [result, profile, activeShocks]
  );

  const timeline = useMemo(
    () => (result ? buildTimeline(result, profile, activeShocks) : []),
    [result, profile, activeShocks]
  );

  const obligations = useMemo(
    () =>
      result
        ? buildObligations(profile, result.baseline.monthlyBufferCents)
        : buildObligations(profile, 0),
    [result, profile]
  );

  const recoveryActions = useMemo(
    () => (result ? buildRecoveryActions(result) : []),
    [result]
  );

  const assumptions = useMemo(
    () => buildAssumptions(activeShocks, months),
    [activeShocks, months]
  );

  const drivers = useMemo(
    () => (result ? buildDrivers(profile, result) : []),
    [result, profile]
  );

  const waterfall = useMemo((): WaterfallStep[] => {
    if (!result) return [];
    const startCash = profile.savings.liquidCents;
    const available = profile.debt.availableCreditCents;
    const end = result.simulation.months.at(-1)?.state;
    const shortfall = result.breakingPoint.overageCents ?? 0;

    const steps: WaterfallStep[] = [
      { label: "Starting liquid cash", amountCents: startCash, kind: "resource" },
      {
        label: "Available credit",
        amountCents: available,
        kind: "resource",
        note: "Borrowing capacity, not savings",
      },
      {
        label: "Monthly buffer × horizon",
        amountCents: result.baseline.monthlyBufferCents * months,
        kind: "resource",
        note: "If no shocks",
      },
    ];

    if (activeShocks.includes("layoff")) {
      const duration = layoffDuration(months);
      steps.push({
        label: "Income loss (layoff window)",
        amountCents:
          -(
            profile.income.monthlyTakeHomeCents -
            SHOCK_PARAMS.layoff.replacementIncomeCents
          ) * duration,
        kind: "drain",
        note: `${duration} months`,
      });
    }
    if (activeShocks.includes("vehicle")) {
      steps.push({
        label: "Vehicle repair",
        amountCents: -SHOCK_PARAMS.vehicle.costCents,
        kind: "drain",
        note: `Month ${SHOCK_PARAMS.vehicle.monthIndex}`,
      });
    }

    steps.push({
      label: end && end.cashCents > 0 ? "Ending cash" : "Shortfall / overage",
      amountCents: result.breakingPoint.triggered ? -shortfall : (end?.cashCents ?? 0),
      kind: "result",
    });

    return steps;
  }, [result, profile, activeShocks, months]);

  const value: DashboardContextValue = {
    profile,
    person,
    months,
    activeShocks,
    setActiveShocks,
    toggleShock,
    result,
    loading,
    error,
    rerun: () => void runPrimary(activeShocks),
    verdict,
    timeline,
    obligations,
    recoveryActions,
    assumptions,
    drivers,
    waterfall,
    scenarioComparison,
    compoundShockNames: COMPOUND_SHOCK_NAMES,
    compoundMatrix,
    creditLimitCents,
    comparisonLoading,
  };

  return (
    <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>
  );
}

export { shockCatalog };
