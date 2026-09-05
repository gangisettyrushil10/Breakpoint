"use client";

import { Card, CardTitle } from "@/components/ui/primitives";
import { money } from "@/lib/format";
import { useDashboard } from "@/components/dashboard/DashboardProvider";

export function ShockWaterfall() {
  const { waterfall } = useDashboard();
  const SCALE = Math.max(1, ...waterfall.map((s) => Math.abs(s.amountCents)));
  const rows = waterfall.map((step, index) => {
    const isResult = step.kind === "result";
    const runningCents = isResult
      ? null
      : waterfall
          .slice(0, index + 1)
          .filter((item) => item.kind !== "result")
          .reduce((total, item) => total + item.amountCents, 0);

    return {
      ...step,
      isResult,
      runningCents,
      positive: step.amountCents > 0,
      width: (Math.abs(step.amountCents) / SCALE) * 100,
    };
  });

  if (waterfall.length === 0) {
    return (
      <Card padded>
        <p className="text-[14px] text-ink-3">Waterfall builds after the live run returns.</p>
      </Card>
    );
  }

  return (
    <Card padded={false}>
      <div className="p-5 pb-0">
        <CardTitle
          aside={<span className="text-[11.5px] text-ink-3">From this simulation</span>}
        >
          Where the buffer went
        </CardTitle>
      </div>

      <div className="px-5 pb-2">
        {rows.map((step) => {
          return (
            <div
              key={step.label}
              className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 py-2.5 ${
                step.isResult ? "mt-1 border-t border-line-strong pt-3.5" : ""
              }`}
            >
              <div className="min-w-0">
                <div className="flex items-baseline gap-2">
                  <span
                    className={`truncate text-[13.5px] ${
                      step.isResult ? "font-medium text-critical" : "text-ink"
                    }`}
                  >
                    {step.label}
                  </span>
                </div>
                {step.note ? (
                  <div className="mt-0.5 text-[11.5px] text-ink-3">{step.note}</div>
                ) : null}
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
                  <div
                    className={`h-full rounded-full ${
                      step.isResult
                        ? "bg-critical"
                        : step.positive
                          ? "bg-stable/80"
                          : "bg-caution/70"
                    }`}
                    style={{ width: `${step.width}%` }}
                  />
                </div>
              </div>

              <div className="text-right">
                <div
                  className={`tnum text-[14px] ${
                    step.isResult
                      ? "font-medium text-critical"
                      : step.positive
                        ? "text-stable"
                        : "text-ink-2"
                  }`}
                >
                  {money(step.amountCents, { sign: true })}
                </div>
                {!step.isResult ? (
                  <div className="tnum mt-0.5 text-[11px] text-ink-3">
                    {money(step.runningCents ?? 0)}
                  </div>
                ) : (
                  <div className="mt-0.5 text-[11px] text-ink-3">
                    {step.amountCents < 0 ? "overage" : "end"}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
