"use client";

import Link from "next/link";
import { money } from "@/lib/format";
import { useDashboard } from "@/components/dashboard/DashboardProvider";
import { useProfile } from "@/components/ProfileProvider";

export function ProfileHeader() {
  const { person, profile, result, loading } = useDashboard();
  const { hasOwnProfile } = useProfile();
  const buffer = result?.baseline.monthlyBufferCents ?? 0;

  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-x-8 gap-y-4 px-5 py-6 sm:px-8">
        <div>
          <div className="flex items-center gap-2.5">
            <span aria-hidden className="block h-3.5 w-[3px] rounded-full bg-accent" />
            <span className="text-[13px] font-medium tracking-tight">BreakPoint</span>
            <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-ink-3">
              {loading ? "simulating…" : "live engine"}
            </span>
          </div>
          {/* The mock persona only describes the demo budget. Once these are the
              user's own numbers, naming a stranger would be a lie on the page. */}
          <h1 className="mt-2.5 text-[19px] font-semibold tracking-tight">
            {hasOwnProfile ? "Your budget" : person.name}
          </h1>
          <p className="mt-0.5 text-[13px] text-ink-2">
            {hasOwnProfile ? (
              <>
                {profile.location.city}, {profile.location.state} ·{" "}
                {profile.household.dependents === 0
                  ? "No dependents"
                  : `${profile.household.dependents} dependent${profile.household.dependents === 1 ? "" : "s"}`}{" "}
                · {profile.household.jobStability} income
              </>
            ) : (
              <>
                {person.age} · {person.occupation} · {person.city}, {person.state} ·{" "}
                {person.household} · demo profile
              </>
            )}
          </p>
        </div>

        <div className="order-last flex flex-wrap gap-2 sm:order-0">
          <Link
            href="/intake"
            className="rounded-lg border border-line bg-surface-1 px-3.5 py-2 text-[13px] text-ink-2 hover:border-line-strong hover:text-ink"
          >
            {hasOwnProfile ? "Edit numbers" : "Use my numbers"}
          </Link>
          <Link
            href="/chat"
            className="rounded-lg border border-line bg-surface-1 px-3.5 py-2 text-[13px] text-ink-2 hover:border-line-strong hover:text-ink"
          >
            Ask about this →
          </Link>
          <Link
            href="/account"
            className="rounded-lg border border-line bg-surface-1 px-3.5 py-2 text-[13px] text-ink-2 hover:border-line-strong hover:text-ink"
          >
            Account
          </Link>
        </div>

        <dl className="flex flex-wrap gap-x-7 gap-y-3">
          <Figure
            label="Take-home"
            value={money(profile.income.monthlyTakeHomeCents)}
            suffix="/mo"
          />
          <Figure label="Surplus" value={money(buffer)} suffix="/mo" />
          <Figure
            label="Debt minimums"
            value={money(profile.debt.minimumPaymentsCents)}
            suffix="/mo"
          />
          <Figure label="Liquid savings" value={money(profile.savings.liquidCents)} />
          <Figure
            label="Credit available"
            value={money(profile.debt.availableCreditCents)}
            suffix={`of ${money(profile.debt.creditCardBalanceCents + profile.debt.availableCreditCents)}`}
          />
        </dl>
      </div>
    </header>
  );
}

function Figure({
  label,
  value,
  suffix,
}: {
  label: string;
  value: string;
  suffix?: string;
}) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className="tnum mt-1 text-[15px]">
        {value}
        {suffix ? <span className="ml-1 text-[11.5px] text-ink-3">{suffix}</span> : null}
      </dd>
    </div>
  );
}
