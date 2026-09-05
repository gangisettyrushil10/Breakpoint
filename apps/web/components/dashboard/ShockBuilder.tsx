"use client";

import { Card } from "@/components/ui/primitives";
import {
  shockCatalog,
  useDashboard,
} from "@/components/dashboard/DashboardProvider";
import type { ShockId } from "@/lib/api/mappers";
import { DEFAULT_ACTIVE_SHOCKS } from "@/lib/api/mappers";

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
  const { activeShocks, setActiveShocks, toggleShock, loading } = useDashboard();

  return (
    <Card padded={false}>
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line p-5">
        <div>
          <h3 className="label text-accent">Build the fire drill</h3>
          <p className="mt-1.5 text-[13px] text-ink-2">
            Toggle realistic setbacks. The cash, credit, and breaking-point timeline recalculates immediately.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setActiveShocks([])}
            aria-pressed={activeShocks.length === 0}
            className={`rounded-md border px-3 py-1.5 text-[12px] transition-colors ${
              activeShocks.length === 0
                ? "border-stable/50 bg-stable-dim text-stable"
                : "border-line bg-surface-2 text-ink-2 hover:border-line-strong"
            }`}
          >
            Calm baseline
          </button>
          <button
            type="button"
            onClick={() => setActiveShocks(DEFAULT_ACTIVE_SHOCKS)}
            aria-pressed={
              activeShocks.length === DEFAULT_ACTIVE_SHOCKS.length &&
              DEFAULT_ACTIVE_SHOCKS.every((id) => activeShocks.includes(id))
            }
            className="rounded-md border border-accent/50 bg-accent-dim px-3 py-1.5 text-[12px] text-accent transition-colors hover:border-accent"
          >
            Demo stack
          </button>
        </div>
      </div>

      <div className="flex items-center justify-between gap-4 border-b border-line bg-surface-2/60 px-5 py-2.5">
        <p className="text-[12px] text-ink-3">
          Baseline score stays fixed; selected shocks test how long the budget survives.
        </p>
        <div className="tnum shrink-0 text-[12px] text-ink-2" aria-live="polite">
          <span className="text-ink">{activeShocks.length}</span> active
          {loading ? <span className="simulation-pulse ml-2 text-accent">recalculating</span> : null}
        </div>
      </div>

      <div className="grid gap-px bg-line sm:grid-cols-2 lg:grid-cols-3">
        {shockCatalog.map((shock) => {
          const on = activeShocks.includes(shock.id);
          return (
            <button
              key={shock.id}
              type="button"
              onClick={() => toggleShock(shock.id as ShockId)}
              aria-pressed={on}
              className={`shock-tile group flex min-h-[92px] flex-col items-start gap-1 bg-surface-1 p-4 text-left transition-all hover:bg-surface-2 ${
                on ? `is-active shock-${shock.category}` : ""
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
                <span
                  className={`text-[10.5px] uppercase tracking-wider ${categoryTone[shock.category]}`}
                >
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
        Every outcome comes from the deterministic engine. Identical inputs always produce identical results.
      </p>
    </Card>
  );
}
