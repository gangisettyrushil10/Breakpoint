import { money } from "@/lib/format";
import {
  person,
  income,
  savings,
  credit,
  monthlyBufferCents,
  debtMinimumsCents,
} from "@/lib/mock/profile";

export function ProfileHeader() {
  return (
    <header className="border-b border-line">
      <div className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-x-8 gap-y-4 px-5 py-6 sm:px-8">
        <div>
          <div className="flex items-center gap-2.5">
            <span aria-hidden className="block h-3.5 w-[3px] rounded-full bg-accent" />
            <span className="text-[13px] font-medium tracking-tight">BreakPoint</span>
            <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-ink-3">
              demo profile
            </span>
          </div>
          <h1 className="mt-2.5 text-[19px] font-semibold tracking-tight">{person.name}</h1>
          <p className="mt-0.5 text-[13px] text-ink-2">
            {person.age} · {person.occupation} · {person.city}, {person.state} ·{" "}
            {person.household}
          </p>
        </div>

        <dl className="flex flex-wrap gap-x-7 gap-y-3">
          <Figure label="Take-home" value={money(income.monthlyTakeHomeCents)} suffix="/mo" />
          <Figure label="Surplus" value={money(monthlyBufferCents)} suffix="/mo" />
          <Figure label="Debt minimums" value={money(debtMinimumsCents)} suffix="/mo" />
          <Figure label="Liquid savings" value={money(savings.liquidCents)} />
          <Figure
            label="Credit available"
            value={money(credit.availableCents)}
            suffix={`of ${money(credit.limitCents)}`}
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
