"use client";

import { Card, RiskPill, Stat, FaultLine } from "@/components/ui/primitives";
import { months } from "@/lib/format";
import { useDashboard } from "@/components/dashboard/DashboardProvider";

function PressureBar({ breakAt, horizon }: { breakAt: number; horizon: number }) {
  const safe = Math.min(100, (breakAt / horizon) * 100);
  return (
    <div className="mt-6">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface-3">
        <div className="bg-stable/70" style={{ width: `${safe}%` }} />
        <div aria-hidden className="w-[2px] bg-bg" />
        <div className="flex-1 bg-critical/60" />
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-ink-3">
        <span>Month 0</span>
        <span className="text-caution">
          {breakAt < horizon ? `Pressure at month ${breakAt}` : "Holds through horizon"}
        </span>
        <span>Month {horizon}</span>
      </div>
    </div>
  );
}

export function ResilienceVerdict() {
  const { verdict, person, result, months: horizon, loading, error } = useDashboard();

  if (error) {
    return (
      <Card padded>
        <p className="text-[14px] text-critical">Could not reach the simulator: {error}</p>
        <p className="mt-2 text-[13px] text-ink-3">
          Is the API running at http://localhost:8000?
        </p>
      </Card>
    );
  }

  if (loading || !verdict || !result) {
    return (
      <Card padded>
        <p className="text-[14px] text-ink-3">Computing resilience from live engine…</p>
      </Card>
    );
  }

  return (
    <Card className="rise" padded={false}>
      <div className="p-6 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="label">Resilience verdict</div>
          <div className="flex items-center gap-2">
            <span className="tnum rounded bg-surface-2 px-2 py-0.5 text-[11px] text-ink-2">
              Score {verdict.score}
            </span>
            <RiskPill state={verdict.riskState} />
          </div>
        </div>

        <p className="mt-4 max-w-[26ch] text-balance text-[30px] leading-[1.15] font-semibold tracking-tight sm:max-w-[34ch] sm:text-[38px]">
          {verdict.headline}
        </p>

        <p className="mt-4 max-w-[64ch] text-[15px] leading-relaxed text-ink-2">
          Live run for {person.name.split(" ")[0]}: runway{" "}
          {verdict.baselineRunwayMonths.toFixed(1)} months of essentials, monthly buffer{" "}
          ${(result.baseline.monthlyBufferCents / 100).toFixed(0)}. Numbers come from{" "}
          <span className="text-ink">POST /simulate</span> — not the LLM.
        </p>

        <PressureBar breakAt={verdict.monthsUntilMissedPayment} horizon={horizon} />
      </div>

      <FaultLine />

      <div className="grid grid-cols-2 gap-6 p-6 sm:p-8 lg:grid-cols-4">
        <Stat
          value={months(verdict.monthsUntilCashOut)}
          label="Until cash runs out"
          tone="caution"
          hint="Liquid savings only"
        />
        <Stat
          value={months(verdict.monthsUntilMissedPayment)}
          label="Until credit pressure"
          tone="critical"
          hint="Limit / breaking point"
        />
        <Stat
          value={String(verdict.shocksSurvivable)}
          label="Active shocks"
          hint="From shock builder"
        />
        <Stat
          value={months(verdict.baselineRunwayMonths)}
          label="If income stopped today"
          hint="No shock timing assumed"
        />
      </div>

      <FaultLine />

      <div className="flex flex-col gap-2 p-6 sm:flex-row sm:items-start sm:gap-6 sm:p-8">
        <div className="label shrink-0 pt-0.5">Weakest link</div>
        <div>
          <div className="text-[15px] font-medium text-caution">{verdict.primaryWeakness}</div>
          <p className="mt-1 max-w-[64ch] text-[14px] leading-relaxed text-ink-2">
            {verdict.weaknessDetail}
          </p>
        </div>
      </div>
    </Card>
  );
}
