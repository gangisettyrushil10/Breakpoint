"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/primitives";
import { money, months } from "@/lib/format";
import { useDashboard } from "@/components/dashboard/DashboardProvider";

const effortMeta = {
  low: { label: "Low effort", cls: "text-stable" },
  medium: { label: "Medium effort", cls: "text-caution" },
  high: { label: "High effort", cls: "text-accent" },
} as const;

export function RecoveryComparison() {
  const { recoveryActions, result, months: horizon } = useDashboard();
  const [open, setOpen] = useState<string | null>(null);

  if (recoveryActions.length === 0) {
    return (
      <Card padded>
        <p className="text-[14px] text-ink-3">Prevention plan unavailable until a run completes.</p>
      </Card>
    );
  }

  const overage = result?.breakingPoint.overageCents ?? 0;
  const saveAction = recoveryActions.find((a) => a.id === "save");

  return (
    <Card padded={false}>
      <div className="p-5 pb-0">
        <CardTitle
          aside={<span className="text-[11.5px] text-ink-3">From prevention engine</span>}
        >
          What each change buys you
        </CardTitle>
      </div>

      <div className="divide-y divide-line">
        {recoveryActions.map((action) => {
          const survives = action.monthsUntilMissedPayment === null;
          const value = action.monthsUntilMissedPayment ?? horizon;
          const width = (value / horizon) * 100;
          const isCurrent = action.id === "current";
          const isOpen = open === action.id;

          return (
            <button
              key={action.id}
              type="button"
              onClick={() => setOpen(isOpen ? null : action.id)}
              aria-expanded={isOpen}
              className="block w-full px-5 py-3.5 text-left transition-colors hover:bg-surface-2"
            >
              <div className="flex items-baseline justify-between gap-4">
                <span
                  className={`text-[14px] ${
                    isCurrent ? "text-ink-2" : "font-medium text-ink"
                  }`}
                >
                  {action.label}
                  {isCurrent ? (
                    <span className="ml-2 text-[11px] text-ink-3">baseline</span>
                  ) : null}
                </span>
                <span
                  className={`tnum shrink-0 text-[13.5px] ${
                    survives ? "text-stable" : isCurrent ? "text-critical" : "text-caution"
                  }`}
                >
                  {survives ? "Survives" : months(value)}
                </span>
              </div>

              <div className="mt-2 flex items-center gap-3">
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-3">
                  <div
                    className={`h-full rounded-full transition-[width] duration-500 ${
                      survives ? "bg-stable/80" : isCurrent ? "bg-critical/70" : "bg-caution/70"
                    }`}
                    style={{ width: `${width}%` }}
                  />
                </div>
                <span
                  className={`w-[86px] shrink-0 text-right text-[11.5px] ${
                    survives ? "text-stable" : "tnum text-ink-3"
                  }`}
                >
                  {action.deltaLabel}
                </span>
              </div>

              {isOpen ? (
                <div className="mt-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span
                    className={`text-[11px] uppercase tracking-wider ${effortMeta[action.effort].cls}`}
                  >
                    {effortMeta[action.effort].label}
                  </span>
                  <p className="max-w-[62ch] text-[13px] leading-relaxed text-ink-2">
                    {action.detail}
                  </p>
                </div>
              ) : null}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2 border-t border-line px-5 py-3">
        <span className="size-1.5 rounded-full bg-stable" />
        <p className="text-[12.5px] text-ink-3">
          {saveAction && overage > 0 ? (
            <>
              Raising the emergency fund by{" "}
              <span className="tnum text-ink-2">
                {money(result?.preventionPlan?.extraSavingsCentsNeeded ?? overage)}
              </span>{" "}
              clears the{" "}
              <span className="tnum text-ink-2">{money(overage)}</span> overage from the
              live breaking-point search.
            </>
          ) : result?.breakingPoint.triggered ? (
            <>Prevention levers come from the deterministic overage in this run.</>
          ) : (
            <>No severe-risk trigger — keep the buffer and re-test with harder shocks.</>
          )}
        </p>
      </div>
    </Card>
  );
}
