"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Explain } from "@/components/ui/Explain";
import { budgetProgress } from "@/lib/budget-progress";
import { money } from "@/lib/format";
import type { FinancialProfile, SimulateResponse } from "@/lib/api/types";

/**
 * The picture being built, shown beside the conversation.
 *
 * Two jobs. It answers "how much longer is this going to take?", which is the
 * one thing a form does better than a chat. And it makes each answer visibly
 * land — a row that has just changed flashes, so the reply and the effect are
 * connected rather than the panel silently drifting.
 *
 * Every figure here is read from the profile or the engine result. Nothing on
 * this panel is computed locally beyond formatting.
 */

const FLASH_MS = 1400;

function useRecentlyChanged(values: Record<string, number>): Set<string> {
  const previous = useRef<Record<string, number> | null>(null);
  const [changed, setChanged] = useState<Set<string>>(new Set());

  useEffect(() => {
    const before = previous.current;
    previous.current = values;

    // First render is not a change — everything would flash at once.
    if (before === null) return;

    const moved = Object.keys(values).filter((key) => values[key] !== before[key]);
    if (moved.length === 0) return;

    setChanged(new Set(moved));
    const timer = setTimeout(() => setChanged(new Set()), FLASH_MS);
    return () => clearTimeout(timer);
  }, [values]);

  return changed;
}

function ScoreDial({ score }: { score: number | null }) {
  // A ring rather than a number alone: "48" means nothing to someone who has
  // never seen a resilience score, but a part-filled ring reads instantly.
  const pct = score === null ? 0 : Math.max(0, Math.min(100, score)) / 100;
  const tone =
    score === null
      ? "var(--color-ink-3)"
      : score >= 70
        ? "var(--color-stable)"
        : score >= 45
          ? "var(--color-caution)"
          : "var(--color-critical)";

  return (
    <div className="flex items-center gap-3">
      <div
        className="relative grid h-14 w-14 place-items-center rounded-full transition-[background] duration-500"
        style={{
          background: `conic-gradient(${tone} ${pct * 360}deg, var(--color-surface-3) 0deg)`,
        }}
      >
        <div className="grid h-11 w-11 place-items-center rounded-full bg-surface-1">
          <span className="tnum text-[15px] font-medium" style={{ color: tone }}>
            {score === null ? "—" : score}
          </span>
        </div>
      </div>
      <div>
        <div className="text-[13px] text-ink-2">
          <Explain term="resilienceScore">How sturdy this is</Explain>
        </div>
        <div className="mt-0.5 text-[11.5px] text-ink-3">
          {score === null ? "Answer a few things first" : "out of 100"}
        </div>
      </div>
    </div>
  );
}

export function BudgetPanel({
  profile,
  result,
}: {
  profile: FinancialProfile;
  result: SimulateResponse | null;
}) {
  const progress = useMemo(() => budgetProgress(profile), [profile]);

  const values = useMemo(
    () => Object.fromEntries(progress.rows.map((row) => [row.id, row.cents])),
    [progress.rows]
  );
  const changed = useRecentlyChanged(values);

  const breaks = result?.breakingPoint.triggered ?? false;
  const breakMonth = (result?.breakingPoint.monthIndex ?? 0) + 1;

  return (
    <aside className="flex flex-col gap-4 lg:sticky lg:top-6">
      <div className="rounded-lg border border-line bg-surface-1 p-5">
        <ScoreDial score={result?.resilience.score ?? null} />

        <div className="mt-4">
          <div className="flex items-baseline justify-between text-[11.5px] text-ink-3">
            <span>What we know about you</span>
            <span className="tnum">
              {progress.known} of {progress.total}
            </span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
            <div
              className="h-full rounded-full bg-accent transition-[width] duration-700 ease-out"
              style={{ width: `${progress.fraction * 100}%` }}
            />
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-line bg-surface-1 p-5">
        <dl className="flex flex-col">
          {progress.rows.map((row) => (
            <div
              key={row.id}
              className={`-mx-2 flex items-baseline justify-between gap-4 rounded px-2 py-1.5 transition-colors duration-500 ${
                changed.has(row.id) ? "bg-accent-dim" : "bg-transparent"
              }`}
            >
              <dt className="text-[13px] text-ink-2">
                {row.explain ? (
                  <Explain term={row.explain}>{row.label}</Explain>
                ) : (
                  row.label
                )}
              </dt>
              <dd
                className={`tnum text-[13px] whitespace-nowrap ${
                  row.known ? "text-ink" : "text-ink-3"
                }`}
              >
                {money(row.cents)}
                {!row.known ? (
                  <span className="ml-1.5 text-[10px] text-ink-3">example</span>
                ) : null}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {result ? (
        <div
          className={`rounded-lg border p-5 ${
            breaks ? "border-critical/40 bg-critical-dim" : "border-stable/40 bg-stable-dim"
          }`}
        >
          <div className="label">{breaks ? "Where it gives" : "Holding"}</div>
          <p className="mt-2 text-[14px] leading-relaxed text-ink-2">
            {breaks ? (
              <>
                A bill would go unpaid around{" "}
                <span className="text-ink">month {breakMonth}</span> if things go
                wrong.{" "}
                <Explain term="breakingPoint">What does that mean?</Explain>
              </>
            ) : (
              <>
                Nothing tested so far breaks this budget.{" "}
                <Explain term="stackedShocks">What was tested?</Explain>
              </>
            )}
          </p>
        </div>
      ) : null}
    </aside>
  );
}
