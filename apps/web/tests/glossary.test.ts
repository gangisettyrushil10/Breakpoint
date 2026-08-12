/**
 * Copy rules, enforced.
 *
 * `lib/glossary.ts` states that a `short` definition must make sense to someone
 * who has never used a budgeting app, and must not lean on another money term to
 * do its work. That is a real constraint and it is easy to break by accident six
 * months from now, so it is checked rather than merely written down.
 */

import { describe, expect, it } from "vitest";
import { GLOSSARY, type GlossaryKey } from "@/lib/glossary";
import { MONEY_GROUPS } from "@/lib/intake";

const entries = Object.entries(GLOSSARY) as [GlossaryKey, (typeof GLOSSARY)[GlossaryKey]][];

/**
 * Words that require prior financial knowledge to parse. They are allowed in
 * `term` (that is the word being explained) and in `detail` (by then the reader
 * has the plain sentence), but never in the plain sentence itself.
 */
const JARGON = [
  "runway",
  "liquid",
  "buffer",
  "utilisation",
  "utilization",
  "amortis",
  "amortiz",
  "deterministic",
  "apr",
  "principal",
  "accrue",
  "accrual",
  "headroom",
  "disposable income",
  "net worth",
];

describe("glossary", () => {
  it("has a term, a plain sentence, and a detail for every entry", () => {
    for (const [key, entry] of entries) {
      expect(entry.term.trim(), `${key}.term`).not.toBe("");
      expect(entry.short.trim(), `${key}.short`).not.toBe("");
      expect(entry.detail.trim(), `${key}.detail`).not.toBe("");
    }
  });

  it("never explains a money word using more jargon", () => {
    for (const [key, entry] of entries) {
      const short = entry.short.toLowerCase();
      for (const word of JARGON) {
        expect(short.includes(word), `${key}.short contains "${word}"`).toBe(false);
      }
    }
  });

  it("keeps the plain sentence short enough to actually read", () => {
    for (const [key, entry] of entries) {
      // One sentence, roughly. Past this it stops being the quick answer and
      // starts being the detail, which has its own field.
      expect(entry.short.length, `${key}.short is too long`).toBeLessThanOrEqual(130);
    }
  });

  it("says more in the detail than in the summary", () => {
    for (const [key, entry] of entries) {
      expect(entry.detail.length, `${key}.detail should expand on short`).toBeGreaterThan(
        entry.short.length
      );
    }
  });

  it("points every intake field's explainer at a real entry", () => {
    const keys = new Set(Object.keys(GLOSSARY));
    for (const group of MONEY_GROUPS) {
      for (const field of group.money) {
        if (!field.explain) continue;
        expect(keys.has(field.explain), `${field.key} -> ${field.explain}`).toBe(true);
      }
    }
  });
});
