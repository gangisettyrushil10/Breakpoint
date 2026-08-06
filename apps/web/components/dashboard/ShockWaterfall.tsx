import { Card, CardTitle } from "@/components/ui/primitives";
import { money } from "@/lib/format";
import { waterfall } from "@/lib/mock/profile";

/*
  Horizontal rather than the usual vertical waterfall: the labels are long,
  and the running total is the point — the reader should watch capacity build
  and then get consumed, ending below zero.
*/
const SCALE = Math.max(...waterfall.map((s) => Math.abs(s.amountCents)));

export function ShockWaterfall() {
  let running = 0;

  return (
    <Card padded={false}>
      <div className="p-5 pb-0">
        <CardTitle
          aside={<span className="text-[11.5px] text-ink-3">Across 5 crisis months</span>}
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
                  <div className="mt-0.5 text-[11px] text-ink-3">unpaid</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <p className="border-t border-line px-5 py-3 text-[12.5px] text-ink-3">
        Available credit is shown as a resource because it delays the failure — but it is
        borrowed, and the shortfall is what remains after it is fully drawn.
      </p>
    </Card>
  );
}
