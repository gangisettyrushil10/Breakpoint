"use client";

import { Card, CardTitle } from "@/components/ui/primitives";
import { money } from "@/lib/format";
import { useDashboard } from "@/components/dashboard/DashboardProvider";

export function ShockWaterfall() {
  const { waterfall } = useDashboard();
  let running = 0;
  const SCALE = Math.max(1, ...waterfall.map((s) => Math.abs(s.amountCents)));

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
        {waterfall.map((step) => {
          const isResult = step.kind === "result";
          if (!isResult) running += step.amountCents;
          const width = (Math.abs(step.amountCents) / SCALE) * 100;
          const positive = step.amountCents > 0;

          return (
            <div
              key={step.label}
              className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 gap-y-1 py-2.5 ${
                isResult ? "mt-1 border-t border-line-strong pt-3.5" : ""
              }`}
            >
              <div className="min-w-0">
                <div className="flex items-baseline gap-2">
                  <span
                    className={`truncate text-[13.5px] ${
                      isResult ? "font-medium text-critical" : "text-ink"
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
                      isResult ? "bg-critical" : positive ? "bg-stable/80" : "bg-caution/70"
                    }`}
                    style={{ width: `${width}%` }}
                  />
                </div>
              </div>

              <div className="text-right">
                <div
                  className={`tnum text-[14px] ${
                    isResult
                      ? "font-medium text-critical"
                      : positive
                        ? "text-stable"
                        : "text-ink-2"
                  }`}
                >
                  {money(step.amountCents, { sign: true })}
                </div>
                {!isResult ? (
                  <div className="tnum mt-0.5 text-[11px] text-ink-3">{money(running)}</div>
                ) : (
                  <div className="mt-0.5 text-[11px] text-ink-3">
                    {isResult && step.amountCents < 0 ? "overage" : "end"}
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
