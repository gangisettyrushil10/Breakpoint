import type { ReactNode } from "react";
import type { RiskState } from "@/lib/mock/profile";
import { Explain } from "@/components/ui/Explain";
import type { GlossaryKey } from "@/lib/glossary";

export function Section({
  index,
  eyebrow,
  title,
  lede,
  children,
  id,
  collapsible = false,
  openLabel = "Show me the detail",
}: {
  index: string;
  eyebrow: string;
  title: string;
  lede?: string;
  children: ReactNode;
  id?: string;
  /**
   * Hide the charts behind a disclosure, leaving only the heading and the
   * plain-language summary.
   *
   * Six sections of charts opening at once is the fastest way to lose somebody
   * who is already anxious about money. The verdict stays open because it is
   * the answer; the workings fold away until asked for.
   */
  collapsible?: boolean;
  openLabel?: string;
}) {
  const heading = (
    <>
      <div className="flex items-baseline gap-3">
        <span className="tnum text-[11px] text-ink-3">{index}</span>
        <span className="label text-accent">{eyebrow}</span>
      </div>
      <h2 className="mt-2 text-balance text-2xl font-semibold tracking-tight sm:text-[28px]">
        {title}
      </h2>
      {lede ? (
        <p className="mt-2 max-w-[62ch] text-[15px] leading-relaxed text-ink-2">{lede}</p>
      ) : null}
    </>
  );

  if (!collapsible) {
    return (
      <section id={id} className="scroll-mt-8">
        {heading}
        <div className="mt-6 min-w-0">{children}</div>
      </section>
    );
  }

  return (
    <section id={id} className="scroll-mt-8">
      {heading}
      {/* Native <details> for the same reasons as Explain: keyboard support,
          screen-reader semantics and find-in-page, none of it reimplemented. */}
      <details className="section-detail mt-5">
        <summary className="explain-summary text-[13px] text-ink-2">
          <span className="explain-word">{openLabel}</span>
          <span aria-hidden className="explain-mark">
            +
          </span>
        </summary>
        <div className="mt-6 min-w-0">{children}</div>
      </details>
    </section>
  );
}

export function Card({
  children,
  className = "",
  padded = true,
}: {
  children: ReactNode;
  className?: string;
  padded?: boolean;
}) {
  return (
    <div
      className={`min-w-0 rounded-lg border border-line bg-surface-1 shadow-[0_1px_2px_rgba(0,0,0,0.4)] ${
        padded ? "p-5" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}

export function CardTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-4 flex items-baseline justify-between gap-4">
      <h3 className="label">{children}</h3>
      {aside}
    </div>
  );
}

const riskTone: Record<RiskState, { bg: string; fg: string; label: string }> = {
  resilient: { bg: "bg-stable-dim", fg: "text-stable", label: "Resilient" },
  stable: { bg: "bg-stable-dim", fg: "text-stable", label: "Stable" },
  strained: { bg: "bg-caution-dim", fg: "text-caution", label: "Strained" },
  critical: { bg: "bg-critical-dim", fg: "text-critical", label: "Critical" },
};

export function RiskPill({ state, children }: { state: RiskState; children?: ReactNode }) {
  const tone = riskTone[state];
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[12px] font-medium ${tone.bg} ${tone.fg}`}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {children ?? tone.label}
    </span>
  );
}

export function Stat({
  value,
  label,
  tone = "default",
  hint,
  explain,
}: {
  value: string;
  label: string;
  tone?: "default" | "stable" | "caution" | "critical";
  hint?: string;
  /** Makes the label clickable, revealing a plain-language definition. */
  explain?: GlossaryKey;
}) {
  const toneClass = {
    default: "text-ink",
    stable: "text-stable",
    caution: "text-caution",
    critical: "text-critical",
  }[tone];

  return (
    <div>
      <div className={`tnum text-[26px] leading-none font-medium ${toneClass}`}>{value}</div>
      <div className="mt-1.5 text-[13px] text-ink-2">
        {explain ? <Explain term={explain}>{label}</Explain> : label}
      </div>
      {hint ? <div className="mt-0.5 text-[11.5px] text-ink-3">{hint}</div> : null}
    </div>
  );
}

export function FaultLine({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`faultline opacity-40 ${className}`} />;
}
