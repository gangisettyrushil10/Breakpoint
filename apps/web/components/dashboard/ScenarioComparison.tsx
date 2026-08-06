"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardTitle } from "@/components/ui/primitives";
import { moneyCompact, money } from "@/lib/format";
import { scenarioComparison } from "@/lib/mock/profile";

/* Categorical palette — validated for CVD separation on the charcoal surface. */
const SERIES = [
  { id: "baseline", label: "No shocks", color: "var(--color-series-1)" },
  { id: "repair", label: "Vehicle repair only", color: "var(--color-series-2)" },
  { id: "layoff", label: "Layoff only", color: "var(--color-series-3)" },
  { id: "compound", label: "Layoff + repair", color: "var(--color-series-4)" },
] as const;

const data = Array.from({ length: 12 }, (_, month) => {
  const row: Record<string, number> = { month };
  for (const series of scenarioComparison) {
    row[series.id] = series.cash[month] / 100;
  }
  return row;
});

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: { dataKey: string; value: number; color: string }[];
  label?: number;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-line bg-surface-2 px-3 py-2 shadow-lg">
      <div className="label mb-1.5">Month {label}</div>
      <div className="flex flex-col gap-1">
        {payload.map((entry) => {
          const series = SERIES.find((s) => s.id === entry.dataKey);
          return (
            <div key={entry.dataKey} className="flex items-center gap-2 text-[12.5px]">
              <span
                className="h-0.5 w-3 shrink-0 rounded-full"
                style={{ background: entry.color }}
              />
              <span className="flex-1 text-ink-2">{series?.label}</span>
              <span className="tnum text-ink">{money(entry.value * 100)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ScenarioComparison() {
  return (
    <Card padded={false}>
      <div className="p-5 pb-0">
        <CardTitle
          aside={
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
              {SERIES.map((s) => (
                <span key={s.id} className="flex items-center gap-1.5 text-[11.5px] text-ink-2">
                  <span
                    className="h-0.5 w-3.5 rounded-full"
                    style={{ background: s.color }}
                  />
                  {s.label}
                </span>
              ))}
            </div>
          }
        >
          Liquid cash — one shock vs. two
        </CardTitle>
      </div>

      <div className="h-[280px] px-2 pb-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 12, right: 20, bottom: 8, left: 4 }}>
            <CartesianGrid stroke="var(--color-line)" vertical={false} />
            <XAxis
              dataKey="month"
              tick={{ fill: "var(--color-ink-3)", fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "var(--color-line-strong)" }}
            />
            <YAxis
              tick={{ fill: "var(--color-ink-3)", fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(v: number) => moneyCompact(v * 100)}
            />
            <Tooltip
              content={<ChartTooltip />}
              cursor={{ stroke: "var(--color-ink-3)", strokeWidth: 1 }}
            />
            {SERIES.map((s) => (
              <Line
                key={s.id}
                type="monotone"
                dataKey={s.id}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--color-bg)" }}
              />
            ))}
            <ReferenceDot
              x={6}
              y={0}
              r={5}
              fill="var(--color-critical)"
              stroke="var(--color-bg)"
              strokeWidth={2}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <p className="border-t border-line px-5 py-3 text-[12.5px] text-ink-3">
        Either shock alone is survivable. Together they are not — the repair lands while cash is
        already draining, and the marked point in month 6 is where credit runs out too.
      </p>
    </Card>
  );
}
