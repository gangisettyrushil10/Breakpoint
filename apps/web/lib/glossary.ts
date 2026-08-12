/**
 * Plain-language definitions for every money word the app puts on screen.
 *
 * The rule for `short`: it must make sense to someone who has never used a
 * budgeting app, has never heard the word "liquid" applied to money, and is
 * possibly reading this while stressed about money. No term is allowed to be
 * defined using another term from this file.
 *
 * `detail` is where the precision goes — how the number is worked out, and what
 * it means for you. Nothing is dumbed away; it is moved one click down, so the
 * surface stays readable and the rigour stays available.
 *
 * Kept out of the components so the wording can be reviewed in one place rather
 * than hunted across a dozen files.
 */

export interface GlossaryEntry {
  /** The word as it appears on screen. */
  term: string;
  /** One sentence. No jargon, no other glossary terms. */
  short: string;
  /** How it is worked out and why it matters. */
  detail: string;
}

export const GLOSSARY = {
  resilienceScore: {
    term: "Resilience score",
    short:
      "A 0–100 rating of how well your money would hold up if something went wrong.",
    detail:
      "It is built from three things: how long your savings would last, how much you have left over each month, and how much of your credit card is still unused. Higher is safer. It is worked out with fixed arithmetic, so the same numbers always give the same score — nothing here is a guess or an opinion.",
  },
  runway: {
    term: "Runway",
    short: "How long your savings would last if your pay stopped tomorrow.",
    detail:
      "We take the money you could actually spend this week and divide it by what you must pay each month to keep the lights on. Two months of runway means that if your income stopped, you could cover the necessary bills for about two months before the money was gone. It ignores anything you could not reach quickly, like a retirement account.",
  },
  buffer: {
    term: "Monthly buffer",
    short: "What is left over in a normal month once every bill is paid.",
    detail:
      "Your take-home pay minus everything going out — rent, food, transport, insurance, subscriptions, and the minimum payments on any debt. A positive buffer means a normal month adds to your savings. It is worth knowing that a healthy buffer and a thin cushion of savings can happen together, and that combination is exactly what this tool is built to catch.",
  },
  essentials: {
    term: "Essentials",
    short: "The bills you cannot simply stop paying.",
    detail:
      "Rent, utilities, insurance, food, getting to work, and the minimum payments on your debts. Subscriptions and spending money are not counted here, because those are things you could pause in a bad month. Runway is measured against essentials only, on the assumption that if income stopped you would cut the rest first.",
  },
  liquidSavings: {
    term: "Savings you can reach",
    short: "Money you could actually spend this week if you had to.",
    detail:
      "A current account, a normal savings account, cash. Not a pension or retirement account, not money tied up in a property, not anything that would take weeks or a penalty to get at. Only money you could reach in a hurry helps in an emergency, so only that is counted.",
  },
  shock: {
    term: "Shock",
    short: "One bad thing that costs money.",
    detail:
      "A car that needs repairing, a medical bill, the rent going up, losing your job. Each one has a size and a month it lands in, so a $600 repair next month is a different test from a $600 repair in half a year.",
  },
  stackedShocks: {
    term: "Stacked shocks",
    short: "More than one bad thing happening close together.",
    detail:
      "Bad luck does not politely queue up. A single setback is usually survivable; the same setbacks landing in the same few months often are not, because the first one eats the savings that would have absorbed the second. This is the situation most budgeting tools never test.",
  },
  breakingPoint: {
    term: "Breaking point",
    short:
      "The moment you run out of both savings and credit, and a necessary bill goes unpaid.",
    detail:
      "We add up the setbacks month by month. When your savings hit zero, the shortfall goes onto the credit card. The breaking point is the month the card would go past its limit — because at that point there is nothing left to pay rent or buy food with. We look for the smallest, most ordinary run of bad luck that gets you there, not the worst case imaginable.",
  },
  creditDelays: {
    term: "Credit delays it, it does not prevent it",
    short: "A credit card buys you time, not safety.",
    detail:
      "When savings run out, the shortfall moves onto the card and the bills keep getting paid for a while. That is why running out of cash and running out of credit are shown as two separate moments. Credit pushes the breaking point later — and makes it more expensive when it arrives, because the balance is still owed with interest on top.",
  },
  availableCredit: {
    term: "Available credit",
    short: "How much your credit card could still cover in an emergency.",
    detail:
      "This matters as much as what you already owe. Two people with the same savings and the same debt can have very different breaking points if one has far more room left on the card. Once that room is gone, there is nothing between you and an unpaid bill.",
  },
  debtMinimums: {
    term: "Minimum payments",
    short: "The smallest amount you must pay on your debts each month.",
    detail:
      "These are counted as an essential, because they keep coming whether or not you are being paid. They are one of the reasons losing your income is so much harsher than an unexpected one-off bill — the one-off ends, the minimums do not.",
  },
  apr: {
    term: "Interest rate (APR)",
    short: "The yearly rate your credit card charges on money you owe.",
    detail:
      "Recorded because it shapes how expensive it is to lean on the card. In the current version of the model the projection does not add interest on top month by month, which means the picture it paints is, if anything, slightly kinder than reality.",
  },
  cuttable: {
    term: "Spending you could cut",
    short: "Money you could stop spending quickly if you had to.",
    detail:
      "Subscriptions and everyday spending money. Rent and insurance are not in here, because you cannot cancel them this afternoon. This matters for the plan below: if the amount you would need to cut is larger than the amount you actually could cut, then cutting back is not a real option and no amount of budgeting advice will change that.",
  },
  preventionPlan: {
    term: "What would have prevented it",
    short:
      "The exact amount of extra savings, or monthly cutback, that would have stopped the break.",
    detail:
      "Worked out directly from how far past the limit you went, not estimated. It comes in two forms: a one-off amount you would have needed saved beforehand, or a monthly amount you would have needed to stop spending. If the monthly figure is larger than what you could realistically cut, we say so plainly rather than suggesting something impossible.",
  },
  deterministic: {
    term: "Same answer every time",
    short: "The same numbers always produce the same result.",
    detail:
      "Every figure here comes from plain arithmetic that can be traced and checked, not from an AI guessing. The chat assistant is allowed to explain these results, but it cannot invent a single number — it has no access to your budget except by asking the calculator, and any reply containing a figure the calculator did not produce is withheld.",
  },
} as const;

export type GlossaryKey = keyof typeof GLOSSARY;

export function glossary(key: GlossaryKey): GlossaryEntry {
  return GLOSSARY[key];
}
