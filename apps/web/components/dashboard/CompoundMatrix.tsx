import { Card, CardTitle } from "@/components/ui/primitives";
import { compoundMatrix, shockNames } from "@/lib/mock/profile";

/*
  Sequential encoding: one hue, darker = sooner failure. Survivable pairs get
  a neutral surface rather than a hue step, so "no break" never reads as a
  severity level.
*/
function cellStyle(value: number | null) {
  if (value === null) {
    return { background: "var(--color-surface-2)", color: "var(--color-ink-3)" };
  }
  // 6.3 (worst) → 7.0 (best) across the observed range
  const t = Math.min(Math.max((7.0 - value) / 0.7, 0), 1);
  return {
    background: `color-mix(in oklab, var(--color-critical) ${18 + t * 46}%, var(--color-surface-1))`,
    color: "var(--color-ink)",
  };
}

export function CompoundMatrix() {
  return (
    <Card padded={false}>
      <div className="p-5 pb-0">
        <CardTitle aside={<span className="text-[11.5px] text-ink-3">Months to a missed payment</span>}>
          Which pairs break you
        </CardTitle>
      </div>

      <div className="overflow-x-auto px-5 pb-1">
        <table className="w-full min-w-[440px] border-separate border-spacing-[2px]">
          <caption className="sr-only">
            Months until a required payment is missed for each pair of stacked shocks.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="w-[112px]" />
              {shockNames.map((name) => (
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
              <tr key={shockNames[i]}>
                <th
                  scope="row"
                  className="pr-2 text-right text-[12px] font-normal text-ink-2"
                >
                  {shockNames[i]}
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
                          <span className="tnum">{value.toFixed(1)}</span>
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
        Every pair that includes a layoff breaks; no pair without one does. Income loss is the
        multiplier — the expense shocks are only dangerous in its company.
      </p>
    </Card>
  );
}
