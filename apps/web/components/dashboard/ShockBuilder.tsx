"use client";

import { useState } from "react";
import { Card } from "@/components/ui/primitives";
import { shockLibrary } from "@/lib/mock/profile";

const categoryLabel = {
  income: "Income",
  expense: "One-time",
  recurring: "Recurring",
} as const;

const categoryTone = {
  income: "text-critical",
  expense: "text-caution",
  recurring: "text-accent",
} as const;

export function ShockBuilder() {
  const [active, setActive] = useState<string[]>(
    shockLibrary.filter((s) => s.active).map((s) => s.id)
  );

  const toggle = (id: string) =>
    setActive((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-line p-5">
        <div>
          <h3 className="label">Shock library</h3>
          <p className="mt-1.5 text-[13px] text-ink-2">
            Stack events to see how they compound. Ordering by real-world frequency, from the
            Federal Reserve&apos;s 2025 household survey.
          </p>
        </div>
        <div className="tnum text-[13px] text-ink-2">
          <span className="text-ink">{active.length}</span> active
        </div>
      </div>

      <div className="grid gap-px bg-line sm:grid-cols-2 lg:grid-cols-3">
        {shockLibrary.map((shock) => {
          const on = active.includes(shock.id);
          return (
            <button
              key={shock.id}
              type="button"
              onClick={() => toggle(shock.id)}
              aria-pressed={on}
              className={`group flex flex-col items-start gap-1 bg-surface-1 p-4 text-left transition-colors hover:bg-surface-2 ${
                on ? "bg-surface-2" : ""
              }`}
            >
              <div className="flex w-full items-center justify-between gap-2">
                <span
                  className={`text-[14px] font-medium ${on ? "text-ink" : "text-ink-2"}`}
                >
                  {shock.label}
                </span>
                <span
                  aria-hidden
                  className={`flex size-4 shrink-0 items-center justify-center rounded-[4px] border text-[10px] ${
                    on
                      ? "border-accent bg-accent text-bg"
                      : "border-line-strong text-transparent group-hover:border-ink-3"
                  }`}
                >
                  ✓
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-[10.5px] uppercase tracking-wider ${categoryTone[shock.category]}`}>
                  {categoryLabel[shock.category]}
                </span>
                <span className="tnum text-[12px] text-ink-3">{shock.defaultCost}</span>
              </div>
              {shock.prevalence ? (
                <span className="mt-0.5 rounded bg-surface-3 px-1.5 py-0.5 text-[10px] text-ink-3">
                  {shock.prevalence}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      <p className="border-t border-line px-5 py-3 text-[12.5px] text-ink-3">
        Toggling is wired to local state only in this build — the engine call that re-runs the
        simulation is the next integration step.
      </p>
    </Card>
  );
}
