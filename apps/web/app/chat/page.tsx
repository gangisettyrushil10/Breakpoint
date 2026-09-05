import Link from "next/link";
import { ChatSurface } from "@/components/chat/ChatSurface";

export const metadata = {
  title: "Ask BreakPoint — explain my resilience",
  description:
    "Chat with the BreakPoint agent. Every figure comes from the same deterministic simulation engine behind the dashboard.",
};

export default function ChatPage() {
  return (
    <>
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-6 sm:px-8">
          <div>
            <div className="flex items-center gap-2.5">
              <span aria-hidden className="brand-mark block h-3.5 w-[3px] rounded-full bg-accent" />
              <span className="text-[13px] font-medium tracking-tight">BreakPoint</span>
              <span className="rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-ink-3">
                agent
              </span>
            </div>
            <h1 className="mt-2.5 text-[22px] font-semibold tracking-tight">
              Talk it through
            </h1>
            <p className="mt-1 max-w-[54ch] text-[15px] leading-relaxed text-ink-2">
              Tell it about your money in your own words. Everything it says is
              worked out with a calculator, not guessed.
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

      <main className="mx-auto w-full max-w-6xl flex-1 px-5 py-8 sm:px-8">
        <ChatSurface />
      </main>
    </>
  );
}
