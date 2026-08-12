"use client";

import { useState } from "react";
import { useProfile } from "@/components/ProfileProvider";

/**
 * Footer note plus the delete path.
 *
 * ARCHITECTURE.md names privacy and a delete path as a risk to mitigate. While
 * everything lives in `localStorage` this is the whole of it: one button that
 * actually removes the data, rather than a promise that it will be removed.
 */
export function DataFooter() {
  const { hasOwnProfile, clearAll } = useProfile();
  const [confirming, setConfirming] = useState(false);

  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-5 py-6 text-[12px] text-ink-3 sm:px-8">
        <span>
          BreakPoint — short- and medium-term financial resilience under compound
          emergencies
        </span>

        {hasOwnProfile ? (
          confirming ? (
            <span className="flex items-center gap-2">
              <span className="text-ink-2">Delete your saved numbers and chat?</span>
              <button
                type="button"
                onClick={() => {
                  clearAll();
                  setConfirming(false);
                }}
                className="rounded border border-critical/40 px-2 py-1 text-critical hover:bg-critical-dim"
              >
                Delete
              </button>
              <button
                type="button"
                onClick={() => setConfirming(false)}
                className="rounded border border-line px-2 py-1 hover:border-line-strong hover:text-ink"
              >
                Cancel
              </button>
            </span>
          ) : (
            <span className="flex items-center gap-3">
              <span className="tnum">Stored in this browser only</span>
              <button
                type="button"
                onClick={() => setConfirming(true)}
                className="rounded border border-line px-2 py-1 hover:border-line-strong hover:text-ink"
              >
                Clear my data
              </button>
            </span>
          )
        ) : (
          <span className="tnum">Live engine · demo profile</span>
        )}
      </div>
    </footer>
  );
}
