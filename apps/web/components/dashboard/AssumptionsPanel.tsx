"use client";

import { useEffect, useState } from "react";
import { Card, CardTitle } from "@/components/ui/primitives";
import { useDashboard } from "@/components/dashboard/DashboardProvider";

export function AssumptionsPanel() {
  const { assumptions, result } = useDashboard();
  const [runAt, setRunAt] = useState<string>("—");

  useEffect(() => {
    setRunAt(new Date().toISOString());
  }, [result]);

  const receipt = {
    formulaVersion: "sim-engine 0.4.0",
    schemaVersion: 1,
    runAt,
    seed: "deterministic — no sampling",
    sources: [
      "User financial profile (demo Maya Restrepo)",
      "Live POST /simulate response",
      "Fed SHED 2025 — unexpected expense prevalence (shock library labels)",
    ],
    score: result?.resilience.score,
    triggered: result?.breakingPoint.triggered,
  };

  return (
    <Card padded={false}>
      <div className="p-5 pb-0">
        <CardTitle aside={<span className="text-[11.5px] text-ink-3">Challenge any of these</span>}>
          Assumptions behind this run
        </CardTitle>
      </div>

      <dl className="grid gap-px bg-line sm:grid-cols-2">
        {assumptions.map((row) => (
          <div
            key={row.label}
            className="flex items-baseline justify-between gap-4 bg-surface-1 px-5 py-2.5"
          >
            <dt className="text-[13px] text-ink-2">{row.label}</dt>
            <dd className="tnum shrink-0 text-[13px]">{row.value}</dd>
          </div>
        ))}
      </dl>

      <div className="border-t border-line px-5 py-4">
        <div className="label mb-2.5">Scenario receipt</div>
        <div className="grid gap-x-8 gap-y-1.5 sm:grid-cols-2">
          <Row label="Formula version" value={receipt.formulaVersion} />
          <Row label="Schema version" value={`v${receipt.schemaVersion}`} />
          <Row label="Run at" value={receipt.runAt} />
          <Row label="Seed" value={receipt.seed} />
          <Row
            label="Live score"
            value={receipt.score != null ? String(receipt.score) : "—"}
          />
          <Row
            label="Breaking point"
            value={receipt.triggered ? "Triggered" : "Not triggered"}
          />
        </div>
        <div className="mt-3">
          <div className="label mb-1.5">Sources</div>
          <ul className="flex flex-col gap-1">
            {receipt.sources.map((source) => (
              <li key={source} className="text-[12.5px] text-ink-2">
                {source}
              </li>
            ))}
          </ul>
        </div>
        <p className="mt-3 text-[12.5px] text-ink-3">
          Identical inputs always produce identical outputs. No sampling, no model inference —
          every figure on this page traces back to the arithmetic above.
        </p>
      </div>
    </Card>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <span className="text-[12.5px] text-ink-3">{label}</span>
      <span className="tnum shrink-0 text-[12.5px] text-ink-2">{value}</span>
    </div>
  );
}
