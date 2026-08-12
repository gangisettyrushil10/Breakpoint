"use client";

import { Card, CardTitle } from "@/components/ui/primitives";
import { useDashboard } from "@/components/dashboard/DashboardProvider";

function cellStyle(value: number | null) {
  if (value === null) {
    return { background: "var(--color-surface-2)", color: "var(--color-ink-3)" };
  }
  const t = Math.min(Math.max((12 - value) / 12, 0), 1);
  return {
    background: `color-mix(in oklab, var(--color-critical) ${18 + t * 46}%, var(--color-surface-1))`,
    color: "var(--color-ink)",
  };
}

export function CompoundMatrix() {
  const { compoundShockNames, compoundMatrix, comparisonLoading } = useDashboard();

  return (
    <Card padded={false}>
      <div className="p-5 pb-0">
        <CardTitle
          aside={
            <span className="text-[11.5px] text-ink-3">
              {comparisonLoading ? "Computing…" : "Live pair sims"}
            </span>
          }
        >
          Which pairs break you
        </CardTitle>
      </div>

      <div className="overflow-x-auto px-5 pb-1">
        <table className="w-full min-w-[440px] border-separate border-spacing-[2px]">
          <caption className="sr-only">
            Month index of severe risk for each pair of stacked shocks from the live API.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="w-[112px]" />
              {compoundShockNames.map((name) => (
                <th
                  key={name}
                  scope="col"
                  className="pb-1 text-left text-[11px] font-normal text-ink-3"
                >
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {compoundMatrix.map((row, i) => (
              <tr key={compoundShockNames[i]}>
                <th
                  scope="row"
                  className="pr-2 text-right text-[12px] font-normal text-ink-2"
                >
                  {compoundShockNames[i]}
                </th>
                {row.map((value, j) => {
                  const isDiagonal = i === j;
                  return (
                    <td key={j} className="p-0">
                      <div
                        className="flex h-11 items-center justify-center rounded-[3px] text-[13px]"
                        style={
                          isDiagonal
                            ? { background: "var(--color-bg)", color: "var(--color-ink-3)" }
                            : cellStyle(value)
                        }
                      >
                        {isDiagonal ? (
                          <span aria-label="same shock">·</span>
                        ) : value === null ? (
                          <span className="text-[11.5px]">survives</span>
                        ) : (
                          <span className="tnum">{value.toFixed(0)}</span>
                        )}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="border-t border-line px-5 py-3 text-[12.5px] text-ink-3">
        Each off-diagonal cell is a live stacked <span className="text-ink">/simulate</span>{" "}
        run. Numbers are the month index where credit exceeds available limit, or
        &ldquo;survives&rdquo; if it never does.
      </p>
    </Card>
  );
}
