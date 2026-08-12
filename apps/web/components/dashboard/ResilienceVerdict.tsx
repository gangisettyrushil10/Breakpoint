"use client";

import { Card, RiskPill, Stat, FaultLine } from "@/components/ui/primitives";
import { ExplainList } from "@/components/ui/Explain";
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
        <span>Today</span>
        <span className="text-caution">
          {breakAt < horizon
            ? `Trouble starts around month ${breakAt}`
            : `Holds for all ${horizon} months`}
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
          <div className="label">Where you stand</div>
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
          In a normal month, {person.name.split(" ")[0]} has{" "}
          <span className="text-ink">
            ${(result.baseline.monthlyBufferCents / 100).toFixed(0)}
          </span>{" "}
          left over after every bill is paid. But if the money coming in stopped
          tomorrow, savings would cover the bills that cannot be skipped for about{" "}
          <span className="text-ink">
            {verdict.baselineRunwayMonths.toFixed(1)} months
          </span>
          .
        </p>

        <ExplainList
          className="mt-4"
          label="What do these numbers mean?"
          terms={["buffer", "runway", "essentials", "resilienceScore", "deterministic"]}
        />

        <PressureBar breakAt={verdict.monthsUntilMissedPayment} horizon={horizon} />
      </div>

      <FaultLine />

      <div className="grid grid-cols-2 gap-6 p-6 sm:p-8 lg:grid-cols-4">
        <Stat
          value={months(verdict.monthsUntilCashOut)}
          label="Until savings run out"
          tone="caution"
          hint="Money you could spend this week"
          explain="liquidSavings"
        />
        <Stat
          value={months(verdict.monthsUntilMissedPayment)}
          label="Until a bill goes unpaid"
          tone="critical"
          hint="Savings and credit both gone"
          explain="breakingPoint"
        />
        <Stat
          value={String(verdict.shocksSurvivable)}
          label="Bad things being tested"
          hint="Change these below"
          explain="shock"
        />
        <Stat
          value={months(verdict.baselineRunwayMonths)}
          label="If your pay stopped today"
          hint="With no other bad luck"
          explain="runway"
        />
      </div>

      <FaultLine />

      <div className="flex flex-col gap-2 p-6 sm:flex-row sm:items-start sm:gap-6 sm:p-8">
        <div className="label shrink-0 pt-0.5">Your weak spot</div>
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
