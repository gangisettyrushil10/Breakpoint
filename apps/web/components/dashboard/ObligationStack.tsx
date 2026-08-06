import { Card, CardTitle } from "@/components/ui/primitives";
import { money, percent } from "@/lib/format";
import { obligations, income } from "@/lib/mock/profile";

const tierMeta = {
  required: { label: "Required", cls: "bg-critical/70", text: "text-critical" },
  "semi-flexible": { label: "Semi-flexible", cls: "bg-caution/70", text: "text-caution" },
  discretionary: { label: "Discretionary", cls: "bg-accent/70", text: "text-accent" },
  surplus: { label: "Unallocated", cls: "bg-stable/70", text: "text-stable" },
} as const;

const tiers = ["required", "semi-flexible", "discretionary", "surplus"] as const;

export function ObligationStack() {
  const total = income.monthlyTakeHomeCents;
  const byTier = tiers.map((tier) => {
    const items = obligations.filter((o) => o.tier === tier);
    const sum = items.reduce((s, o) => s + o.amountCents, 0);
    return { tier, items, sum, share: sum / total };
  });

  return (
    <Card padded={false}>
      <div className="p-5 pb-0">
        <CardTitle
          aside={
            <span className="tnum text-[11.5px] text-ink-3">
              {money(total)} take-home
            </span>
          }
        >
          Where every dollar is already committed
        </CardTitle>
      </div>

      <div className="px-5">
        {/* stacked bar — 2px gaps so adjacent fills stay legible */}
        <div className="flex h-9 w-full gap-[2px] overflow-hidden rounded-md">
          {byTier.map(({ tier, share }) => (
            <div
              key={tier}
              className={tierMeta[tier].cls}
              style={{ width: `${share * 100}%` }}
              title={`${tierMeta[tier].label} — ${percent(share, 1)}`}
            />
          ))}
        </div>

        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5">
          {byTier.map(({ tier, sum, share }) => (
            <div key={tier} className="flex items-center gap-2">
              <span className={`h-2 w-2 shrink-0 rounded-[2px] ${tierMeta[tier].cls}`} />
              <span className="text-[12.5px] text-ink-2">{tierMeta[tier].label}</span>
              <span className="tnum text-[12.5px] text-ink">{money(sum)}</span>
              <span className="tnum text-[11.5px] text-ink-3">{percent(share, 1)}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-4 divide-y divide-line border-t border-line">
        {byTier.map(({ tier, items }) => (
          <div key={tier} className="px-5 py-3">
            <div className={`label ${tierMeta[tier].text}`}>{tierMeta[tier].label}</div>
            <div className="mt-2 grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
              {items.map((item) => (
                <div key={item.label} className="flex items-baseline justify-between gap-3">
                  <span className="truncate text-[13px] text-ink-2">{item.label}</span>
                  <span className="tnum shrink-0 text-[13px]">{money(item.amountCents)}</span>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      <p className="border-t border-line px-5 py-3 text-[12.5px] text-ink-3">
        Housing and transportation together take{" "}
        <span className="tnum text-ink-2">42.5%</span> of take-home — in line with national
        averages, and the reason the crisis budget cannot be trimmed much further.
      </p>
    </Card>
  );
}
