/**
 * A money word you can click to find out what it means.
 *
 * Built on native `<details>`/`<summary>` rather than React state on purpose:
 * that gives keyboard support, screen-reader semantics, and browser find-in-page
 * (which can open a closed panel to reveal a match) for free, and it still works
 * if hydration is slow or fails. There is no reason to reimplement a disclosure
 * widget badly when the platform ships a correct one.
 *
 * The wording lives in `lib/glossary.ts`, not here.
 */

import type { ReactNode } from "react";
import { glossary, type GlossaryKey } from "@/lib/glossary";

export function Explain({
  term,
  children,
  className = "",
}: {
  term: GlossaryKey;
  /** Override the displayed word — the definition shown is the same either way. */
  children?: ReactNode;
  className?: string;
}) {
  const entry = glossary(term);

  return (
    <details className={`explain ${className}`}>
      <summary
        // Without an accessible name the control reads as just the word, giving
        // no hint that it does anything.
        aria-label={`What does "${entry.term}" mean?`}
        className="explain-summary"
      >
        <span className="explain-word">{children ?? entry.term}</span>
        <span aria-hidden className="explain-mark">
          ?
        </span>
      </summary>

      <div className="explain-panel">
        <p className="text-[14px] leading-relaxed text-ink">{entry.short}</p>
        <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">{entry.detail}</p>
      </div>
    </details>
  );
}

/**
 * A single "what do these words mean?" panel covering several terms at once.
 *
 * Used at the top of a section where explaining each word inline would leave the
 * heading unreadable — the thing being fixed in the first place.
 */
export function ExplainList({
  terms,
  label = "What do these words mean?",
  className = "",
}: {
  terms: GlossaryKey[];
  label?: string;
  className?: string;
}) {
  return (
    <details className={`explain-list ${className}`}>
      <summary className="explain-summary">
        <span className="explain-word">{label}</span>
        <span aria-hidden className="explain-mark">
          ?
        </span>
      </summary>

      <dl className="explain-panel">
        {terms.map((key) => {
          const entry = glossary(key);
          return (
            <div key={key} className="mt-3 first:mt-0">
              <dt className="text-[14px] font-medium text-ink">{entry.term}</dt>
              <dd className="mt-1 text-[13.5px] leading-relaxed text-ink-2">
                {entry.short} {entry.detail}
              </dd>
            </div>
          );
        })}
      </dl>
    </details>
  );
}
