"use client";

import type { CSSProperties } from "react";
import { Card, RiskPill, Stat, FaultLine } from "@/components/ui/primitives";
import { ExplainList } from "@/components/ui/Explain";
import { API_URL } from "@/lib/api/client";
import { months } from "@/lib/format";
import { useDashboard } from "@/components/dashboard/DashboardProvider";

function PressureBar({
  breakAt,
  horizon,
  triggered,
}: {
  breakAt: number;
  horizon: number;
  triggered: boolean;
}) {
  const safe = Math.min(100, (breakAt / horizon) * 100);
  return (
    <div className="mt-6">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-surface-3">
        <div
          className="pressure-safe bg-stable/80"
          style={{ width: `${safe}%` }}
        />
        <div aria-hidden className="w-[2px] bg-bg" />
        <div className={triggered ? "flex-1 bg-critical/70" : "flex-1 bg-stable/35"} />
      </div>
      <div className="mt-2 flex justify-between text-[11px] text-ink-3">
        <span>Today</span>
        <span className="text-caution">
          {triggered
            ? `Trouble starts around month ${breakAt}`
            : `Holds for all ${horizon} months`}
        </span>
        <span>Month {horizon}</span>
      </div>
    </div>
  );
}

function ScoreRing({ score }: { score: number }) {
  const color = score >= 70 ? "var(--color-stable)" : score >= 50 ? "var(--color-caution)" : "var(--color-critical)";
  const style = {
    "--score-target": `${score}%`,
    "--score-color": color,
  } as CSSProperties;

  return (
    <div className="score-ring" style={style} aria-label={`Baseline resilience score ${score} out of 100`}>
      <div className="score-ring-core">
        <span className="tnum text-[32px] leading-none font-semibold">{score}</span>
        <span className="mt-1 text-[10px] uppercase text-ink-3">of 100</span>
      </div>
    </div>
  );
}

function ScoreBreakdown({ result }: { result: NonNullable<ReturnType<typeof useDashboard>["result"]> }) {
  const components = [
    { label: "Emergency runway", score: result.resilience.runwaySubscore, weight: "50%", tone: "bg-stable" },
    { label: "Monthly buffer", score: result.resilience.bufferSubscore, weight: "30%", tone: "bg-accent" },
    { label: "Available credit", score: result.resilience.creditSubscore, weight: "20%", tone: "bg-caution" },
  ];

  return (
    <div className="grid gap-5 p-6 sm:grid-cols-3 sm:p-8">
      {components.map((component) => (
        <div key={component.label}>
          <div className="flex items-baseline justify-between gap-3">
            <span className="text-[13px] text-ink-2">{component.label}</span>
            <span className="tnum text-[11px] text-ink-3">{component.weight} weight</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-3">
            <div
              className={`score-bar h-full rounded-full ${component.tone}`}
              style={{ width: `${component.score}%` }}
            />
          </div>
          <div className="tnum mt-1.5 text-[13px] text-ink">{component.score} / 100</div>
        </div>
      ))}
      <p className="text-[12px] leading-relaxed text-ink-3 sm:col-span-3">
        The baseline score measures the budget itself. One-time shocks move the survival timeline; permanent income, spending, savings, or credit changes move this score.
      </p>
    </div>
  );
}

export function ResilienceVerdict() {
  const { verdict, person, result, activeShocks, months: horizon, loading, error } = useDashboard();

  if (error) {
    return (
      <Card padded>
        <p className="text-[14px] text-critical">Could not reach the simulator: {error}</p>
        <p className="mt-2 text-[13px] text-ink-3">
          Is the API running at {API_URL}?
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

  const resultKey = `${verdict.score}-${result.breakingPoint.monthIndex}-${result.breakingPoint.overageCents}`;

  return (
    <Card key={resultKey} className="rise overflow-hidden border-line-strong" padded={false}>
      <div className="p-6 sm:p-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="label">Baseline resilience</div>
          <div className="flex items-center gap-2">
            <RiskPill state={verdict.riskState} />
          </div>
        </div>

        <div className="mt-5 grid items-center gap-6 sm:grid-cols-[132px_minmax(0,1fr)]">
          <ScoreRing score={verdict.score} />
          <div>
            <p className="max-w-[26ch] text-balance text-[30px] leading-[1.15] font-semibold tracking-tight sm:max-w-[34ch] sm:text-[38px]">
              {verdict.headline}
            </p>

            <p className="mt-4 max-w-[64ch] text-[15px] leading-relaxed text-ink-2">
              In a normal month, {person.name.split(" ")[0]} has{" "}
              <span className="tnum text-ink">
                ${(result.baseline.monthlyBufferCents / 100).toFixed(0)}
              </span>{" "}
              left over after every bill is paid. If income stopped tomorrow, savings would cover essentials for about{" "}
              <span className="tnum text-ink">{verdict.baselineRunwayMonths.toFixed(1)} months</span>.
            </p>
          </div>
        </div>

        <ExplainList
          className="mt-4"
          label="What do these numbers mean?"
          terms={["buffer", "runway", "essentials", "resilienceScore", "deterministic"]}
        />

        <PressureBar
          breakAt={verdict.monthsUntilMissedPayment}
          horizon={horizon}
          triggered={result.breakingPoint.triggered}
        />
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
          value={result.breakingPoint.triggered ? months(verdict.monthsUntilMissedPayment) : `${horizon}+ mo`}
          label="Until a bill goes unpaid"
          tone="critical"
          hint="Savings and credit both gone"
          explain="breakingPoint"
        />
        <Stat
          value={String(verdict.shocksSurvivable)}
          label={result.breakingPoint.triggered ? "Smallest breaking stack" : "Shocks absorbed"}
          hint={`${activeShocks.length} selected below`}
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

      <ScoreBreakdown result={result} />

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
