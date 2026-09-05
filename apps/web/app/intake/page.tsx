import Link from "next/link";
import { IntakeForm } from "@/components/intake/IntakeForm";

export const metadata = {
  title: "Your numbers — BreakPoint",
  description:
    "Enter your income, expenses, debt and savings. BreakPoint stress-tests them against stacked emergencies.",
};

export default function IntakePage() {
  return (
    <>
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-4 px-5 py-6 sm:px-8">
          <div>
            <div className="flex items-center gap-2.5">
              <span aria-hidden className="brand-mark block h-3.5 w-[3px] rounded-full bg-accent" />
              <span className="text-[13px] font-medium tracking-tight">BreakPoint</span>
            </div>
            <h1 className="mt-2.5 text-[19px] font-semibold tracking-tight">
              Your numbers
            </h1>
            <p className="mt-0.5 max-w-[62ch] text-[13px] text-ink-2">
              Rough is fine — you can correct anything later, in the form or by
              telling the assistant. Nothing here leaves your browser.
            </p>
          </div>

          <Link
            href="/"
            className="rounded-lg border border-line bg-surface-1 px-3.5 py-2 text-[13px] text-ink-2 hover:border-line-strong hover:text-ink"
          >
            ← Dashboard
          </Link>
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl flex-1 px-5 py-8 sm:px-8">
        <IntakeForm />
      </main>
    </>
  );
}
