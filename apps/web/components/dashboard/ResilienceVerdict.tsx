import { Card, RiskPill, Stat, FaultLine } from "@/components/ui/primitives";
import { months } from "@/lib/format";
import { verdict, person } from "@/lib/mock/profile";

/** A thin pressure bar: how much of the 12-month horizon survives intact. */
function PressureBar({ breakAt, horizon = 12 }: { breakAt: number; horizon?: number }) {
  const safe = (breakAt / horizon) * 100;
  return (
    <div className="mt-6">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface-3">
        <div className="bg-stable/70" style={{ width: `${safe}%` }} />
        <div aria-hidden className="w-[2px] bg-bg" />
        <div className="flex-1 bg-critical/60" />
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-ink-3">
        <span>Month 0</span>
        <span className="text-caution">Payment missed at month {breakAt}</span>
        <span>Month {horizon}</span>
      </div>
    </div>
  );
}

export function ResilienceVerdict() {
  return (
    <Card className="rise" padded={false}>
      <div className="p-6 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="label">Resilience verdict</div>
          <RiskPill state={verdict.riskState} />
        </div>

        <p className="mt-4 max-w-[26ch] text-balance text-[30px] leading-[1.15] font-semibold tracking-tight sm:max-w-[34ch] sm:text-[38px]">
          {verdict.headline}
        </p>

        <p className="mt-4 max-w-[64ch] text-[15px] leading-relaxed text-ink-2">
          Under the selected scenario, {person.name.split(" ")[0]} absorbs the layoff for four
          months on cash alone. The vehicle repair in month 3 is what removes the margin — from
          there, essentials shift onto revolving credit, and the card reaches its limit before
          income returns.
        </p>

        <PressureBar breakAt={verdict.monthsUntilMissedPayment} />
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
          label="Until a payment is missed"
          tone="critical"
          hint="Credit limit reached"
        />
        <Stat
          value={String(verdict.shocksSurvivable)}
          label="Shocks survivable"
          hint="Two together break it"
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
