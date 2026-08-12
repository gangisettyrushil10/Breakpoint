"use client";

import Link from "next/link";
import { useProfile } from "@/components/ProfileProvider";
import { useDashboard } from "@/components/dashboard/DashboardProvider";

/**
 * Says plainly, above everything else, that none of this is the reader's money.
 *
 * Before this existed the only marker was the words "demo profile" at the end of
 * a grey metadata line, under a stranger's name, on a page otherwise full of
 * confident figures about that stranger's finances. A first-time reader could
 * take the whole dashboard at face value, and the way in was a link styled
 * identically to "Account".
 *
 * Rendered only once hydration has settled: `hasOwnProfile` is false until the
 * store has been read, so showing it earlier would flash this banner at people
 * who do have their own numbers saved.
 */
export function DemoNotice() {
  const { hasOwnProfile, hydrated } = useProfile();
  const { person } = useDashboard();

  if (!hydrated || hasOwnProfile) return null;

  return (
    <div className="border-b border-accent/30 bg-accent-dim">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-8 gap-y-3 px-5 py-3.5 sm:px-8">
        <p className="max-w-[68ch] text-[14px] leading-relaxed text-ink-2">
          <span className="font-medium text-ink">This is an example.</span> Every
          number below belongs to {person.name}, someone we made up — none of it
          is yours. Put your own figures in and the whole page is worked out
          again.
        </p>

        <Link
          href="/intake"
          className="rounded-lg bg-accent px-4 py-2 text-[13px] font-medium whitespace-nowrap text-bg transition-opacity hover:opacity-90"
        >
          Enter your own numbers →
        </Link>
      </div>
    </div>
  );
}
