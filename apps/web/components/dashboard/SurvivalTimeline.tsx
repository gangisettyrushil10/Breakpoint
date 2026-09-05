"use client";

import { useState } from "react";
import { Card, CardTitle } from "@/components/ui/primitives";
import { money, moneyCompact, percent } from "@/lib/format";
import { useDashboard } from "@/components/dashboard/DashboardProvider";

const W = 920;
const PAD_L = 62;
const PAD_R = 20;

const PHASE_Y = 14;
const PHASE_H = 4;
const EVENT_Y = 32;

const CASH_TOP = 44;
const CASH_H = 126;
const CASH_BOTTOM = CASH_TOP + CASH_H;

const CREDIT_TOP = 196;
const CREDIT_H = 40;
const CREDIT_BOTTOM = CREDIT_TOP + CREDIT_H;

const AXIS_Y = 254;
const H = 264;

function utilizationColor(u: number) {
  if (u >= 0.99) return "var(--color-critical)";
  if (u >= 0.8) return "var(--color-caution)";
  return "var(--color-accent)";
}

export function SurvivalTimeline() {
  const { timeline, creditLimitCents, result, loading } = useDashboard();
  const [hover, setHover] = useState<number | null>(null);

  if (loading && timeline.length === 0) {
    return (
      <Card padded>
        <p className="text-[14px] text-ink-3">Running simulation…</p>
      </Card>
    );
  }

  if (timeline.length === 0) {
    return (
      <Card padded>
        <p className="text-[14px] text-ink-3">No timeline data yet.</p>
      </Card>
    );
  }

  const LAST = timeline.length - 1;
  const STEP = (W - PAD_L - PAD_R) / timeline.length;
  const x = (m: number) => PAD_L + STEP * (m + 0.5);
  const CASH_MAX = Math.max(
    1_000_000,
    ...timeline.map((d) => d.cashCents),
    100_000
  );
  const yCash = (cents: number) => CASH_BOTTOM - (cents / CASH_MAX) * CASH_H;
  const bandStart = (m: number) => PAD_L + STEP * m;
  const bandEnd = (m: number) => PAD_L + STEP * (m + 1);

  const crisisMonths = timeline.filter((d) => d.phase === "crisis").map((d) => d.month);
  const crisisFrom = crisisMonths.length ? Math.min(...crisisMonths) : -1;
  const crisisTo = crisisMonths.length ? Math.max(...crisisMonths) : -1;

  const phases = [
    { from: 0, to: Math.max(0, crisisFrom - 1), label: "Normal", color: "var(--color-ink-3)" },
    ...(crisisFrom >= 0
      ? [{ from: crisisFrom, to: crisisTo, label: "Crisis", color: "var(--color-critical)" }]
      : []),
    ...(crisisTo >= 0 && crisisTo < LAST
      ? [
          {
            from: crisisTo + 1,
            to: LAST,
            label: "Recovery",
            color: "var(--color-stable)",
          },
        ]
      : []),
  ].filter((p) => p.to >= p.from);

  const cashPath = timeline
    .map((d, i) => `${i === 0 ? "M" : "L"}${x(d.month)} ${yCash(d.cashCents)}`)
    .join(" ");
  const cashArea = `${cashPath} L${x(LAST)} ${CASH_BOTTOM} L${x(0)} ${CASH_BOTTOM} Z`;

  const events = timeline.filter((d) => d.event);
  const active = hover !== null ? timeline[hover] : null;
  const cashOutMonth = timeline.find((d) => d.cashCents <= 0)?.month;
  const breakMonth = result?.breakingPoint.monthIndex;
  const overage = result?.breakingPoint.overageCents ?? 0;

  return (
    <Card padded={false}>
      <div className="p-5 pb-1">
        <CardTitle
          aside={
            <div className="flex flex-wrap items-center gap-4 text-[11.5px] text-ink-2">
              <span className="flex items-center gap-1.5">
                <span className="h-0.5 w-3.5 rounded-full bg-accent" />
                Liquid cash
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-[2px] bg-caution" />
                Credit drawn
              </span>
            </div>
          }
        >
          Survival timeline · {timeline.length} months
        </CardTitle>
      </div>

      <div
        className="overflow-x-auto px-5 pb-2"
        tabIndex={0}
        aria-label="Scrollable survival timeline"
      >
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full min-w-[680px]"
          role="img"
          aria-label="Liquid cash and credit utilization across the simulation horizon."
          onMouseLeave={() => setHover(null)}
        >
          {phases.map((phase) => {
            const x0 = bandStart(phase.from);
            const x1 = bandEnd(phase.to);
            return (
              <g key={phase.label}>
                <rect
                  x={x0}
                  y={PHASE_Y}
                  width={Math.max(0, x1 - x0 - 3)}
                  height={PHASE_H}
                  rx={2}
                  fill={phase.color}
                  opacity={0.5}
                />
                <text
                  x={x0 + 1}
                  y={PHASE_Y - 5}
                  fontSize={9.5}
                  letterSpacing="0.08em"
                  fill={phase.color}
                  opacity={0.9}
                >
                  {phase.label.toUpperCase()}
                </text>
              </g>
            );
          })}

          {crisisFrom >= 0 ? (
            <rect
              x={bandStart(crisisFrom)}
              y={CASH_TOP - 6}
              width={bandEnd(crisisTo) - bandStart(crisisFrom)}
              height={CREDIT_BOTTOM - CASH_TOP + 6}
              fill="var(--color-critical)"
              opacity={0.035}
            />
          ) : null}

          {[0, 0.5, 1].map((f) => {
            const gy = CASH_BOTTOM - f * CASH_H;
            return (
              <g key={f}>
                <line
                  x1={PAD_L}
                  x2={W - PAD_R}
                  y1={gy}
                  y2={gy}
                  stroke="var(--color-line)"
                  strokeWidth={1}
                />
                <text
                  x={PAD_L - 10}
                  y={gy + 3.5}
                  textAnchor="end"
                  className="tnum"
                  fontSize={10}
                  fill="var(--color-ink-3)"
                >
                  {moneyCompact(f * CASH_MAX)}
                </text>
              </g>
            );
          })}
          <text
            x={PAD_L - 10}
            y={CASH_TOP - 8}
            textAnchor="end"
            fontSize={9.5}
            letterSpacing="0.06em"
            fill="var(--color-accent)"
          >
            CASH
          </text>

          <defs>
            <linearGradient id="cashFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--color-accent)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0.02" />
            </linearGradient>
          </defs>
          <path className="timeline-area" d={cashArea} fill="url(#cashFill)" />
          <path
            className="timeline-path"
            d={cashPath}
            pathLength={1}
            fill="none"
            stroke="var(--color-accent)"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {events.map((d) => {
            const isBreak =
              d.event!.includes("exhausted") || d.event!.includes("missed");
            const color = isBreak ? "var(--color-critical)" : "var(--color-ink-3)";
            return (
              <g key={`${d.month}-${d.event}`}>
                <line
                  x1={x(d.month)}
                  x2={x(d.month)}
                  y1={EVENT_Y + 4}
                  y2={CREDIT_BOTTOM}
                  stroke={color}
                  strokeWidth={1}
                  strokeDasharray="3 3"
                  opacity={isBreak ? 0.85 : 0.35}
                />
                <circle cx={x(d.month)} cy={EVENT_Y} r={2.5} fill={color} />
              </g>
            );
          })}

          {cashOutMonth != null ? (
            <>
              <circle
                cx={x(cashOutMonth)}
                cy={yCash(0)}
                r={3.5}
                fill="var(--color-critical)"
              />
              <circle
                cx={x(cashOutMonth)}
                cy={yCash(0)}
                r={6.5}
                fill="none"
                stroke="var(--color-critical)"
                strokeWidth={1}
                opacity={0.45}
              />
            </>
          ) : null}

          <text
            x={PAD_L - 10}
            y={CREDIT_TOP + 4}
            textAnchor="end"
            fontSize={9.5}
            letterSpacing="0.06em"
            fill="var(--color-caution)"
          >
            CREDIT
          </text>
          {timeline.map((d) => {
            const bw = STEP - 14;
            const bh = Math.max(d.utilization * CREDIT_H, 2);
            return (
              <rect
                key={d.month}
                className="timeline-bar"
                x={x(d.month) - bw / 2}
                y={CREDIT_BOTTOM - bh}
                width={bw}
                height={bh}
                rx={2}
                fill={utilizationColor(d.utilization)}
                opacity={hover === null || hover === d.month ? 0.9 : 0.35}
                style={{ animationDelay: `${d.month * 35}ms` }}
              />
            );
          })}
          <line
            x1={PAD_L}
            x2={W - PAD_R}
            y1={CREDIT_BOTTOM}
            y2={CREDIT_BOTTOM}
            stroke="var(--color-line-strong)"
            strokeWidth={1}
          />
          <line
            x1={PAD_L}
            x2={W - PAD_R}
            y1={CREDIT_TOP}
            y2={CREDIT_TOP}
            stroke="var(--color-critical)"
            strokeWidth={1}
            strokeDasharray="2 3"
            opacity={0.75}
          />
          <text
            x={W - PAD_R}
            y={CREDIT_TOP - 5}
            textAnchor="end"
            fontSize={9.5}
            fill="var(--color-critical)"
          >
            LIMIT {moneyCompact(creditLimitCents)}
          </text>

          {timeline.map((d) => (
            <text
              key={d.month}
              x={x(d.month)}
              y={AXIS_Y}
              textAnchor="middle"
              className="tnum"
              fontSize={10}
              fill={hover === d.month ? "var(--color-ink)" : "var(--color-ink-3)"}
            >
              {d.month}
            </text>
          ))}
          <text
            x={PAD_L - 10}
            y={AXIS_Y}
            textAnchor="end"
            fontSize={9.5}
            fill="var(--color-ink-3)"
          >
            MO
          </text>

          {active ? (
            <>
              <line
                x1={x(active.month)}
                x2={x(active.month)}
                y1={EVENT_Y + 4}
                y2={CREDIT_BOTTOM}
                stroke="var(--color-ink-2)"
                strokeWidth={1}
                opacity={0.45}
              />
              <circle
                cx={x(active.month)}
                cy={yCash(active.cashCents)}
                r={4}
                fill="var(--color-accent)"
                stroke="var(--color-bg)"
                strokeWidth={2}
              />
            </>
          ) : null}

          {timeline.map((d) => (
            <rect
              key={d.month}
              x={x(d.month) - STEP / 2}
              y={EVENT_Y - 6}
              width={STEP}
              height={CREDIT_BOTTOM - EVENT_Y + 10}
              fill="transparent"
              onPointerEnter={() => setHover(d.month)}
              onClick={() => setHover(d.month)}
            />
          ))}
        </svg>
      </div>

      <div className="border-t border-line px-5 py-3">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
          <div className="min-w-[64px]">
            <div className="label">Month</div>
            <div className="tnum text-[15px]">{active ? active.month : "—"}</div>
          </div>
          <div className="min-w-[104px]">
            <div className="label">Liquid cash</div>
            <div className="tnum text-[15px] text-accent">
              {active ? money(active.cashCents) : "—"}
            </div>
          </div>
          <div className="min-w-[136px]">
            <div className="label">Credit drawn</div>
            <div className="tnum text-[15px] text-caution">
              {active
                ? `${money(active.creditUsedCents)} · ${percent(active.utilization)}`
                : "—"}
            </div>
          </div>
          <div className="min-w-[92px]">
            <div className="label">Unpaid</div>
            <div
              className={`tnum text-[15px] ${
                active && active.arrearsCents > 0 ? "text-critical" : "text-ink-3"
              }`}
            >
              {active ? money(active.arrearsCents) : "—"}
            </div>
          </div>
          <div className="flex-1 text-[13px]">
            {active?.event ? (
              <span className="text-ink">{active.event}</span>
            ) : (
              <span className="text-ink-3">Hover or tap the chart to inspect a month</span>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-px border-t border-line bg-line sm:grid-cols-2">
        <div className="bg-surface-1 p-4">
          <div className="flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-caution" />
            <span className="label text-caution">First failure</span>
          </div>
          <p className="mt-1.5 text-[14px] text-ink-2">
            {cashOutMonth != null ? (
              <>
                <span className="tnum text-ink">Month {cashOutMonth}</span> — liquid cash
                reaches zero. Essentials begin moving onto the credit card.
              </>
            ) : (
              <>Cash stays positive across the simulated horizon.</>
            )}
          </p>
        </div>
        <div className="bg-surface-1 p-4">
          <div className="flex items-center gap-2">
            <span className="size-1.5 rounded-full bg-critical" />
            <span className="label text-critical">Breaking point</span>
          </div>
          <p className="mt-1.5 text-[14px] text-ink-2">
            {breakMonth != null && result?.breakingPoint.triggered ? (
              <>
                <span className="tnum text-ink">Month {breakMonth}</span> — credit exceeds
                available limit
                {overage > 0 ? (
                  <>
                    {" "}
                    with <span className="tnum">{money(overage)}</span> overage
                  </>
                ) : null}
                .
              </>
            ) : (
              <>No severe-risk trigger in this run.</>
            )}
          </p>
        </div>
      </div>
    </Card>
  );
}
