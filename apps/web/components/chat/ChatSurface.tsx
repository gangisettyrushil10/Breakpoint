"use client";

import { useCallback, useState } from "react";
import Link from "next/link";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { BudgetPanel } from "@/components/chat/BudgetPanel";
import { useProfile } from "@/components/ProfileProvider";
import type { SimulateResponse } from "@/lib/api/types";

/**
 * Client shim between the (server-rendered) chat page and the panel.
 *
 * Hands `ChatPanel` the shared profile and transcript, and holds the latest
 * engine result so `BudgetPanel` can show a live score beside the conversation
 * without issuing a second `/simulate` call of its own.
 */
export function ChatSurface() {
  const {
    profile,
    hasOwnProfile,
    setProfile,
    messages,
    setMessages,
    months,
    hydrated,
  } = useProfile();

  const [result, setResult] = useState<SimulateResponse | null>(null);
  const onResultChange = useCallback(
    (next: SimulateResponse) => setResult(next),
    []
  );

  // Rendering the panel before storage is read would start the conversation
  // against the demo profile and then swap it underneath the user.
  if (!hydrated) {
    return (
      <p className="text-[13px] text-ink-3" role="status">
        Loading your profile…
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {!hasOwnProfile ? (
        <p className="rounded-lg border border-line bg-surface-1 px-4 py-3 text-[13px] leading-relaxed text-ink-2">
          These are still <span className="text-ink">someone else&rsquo;s numbers</span>.
          Just start telling it about yours — try{" "}
          <span className="text-ink">&ldquo;I take home about $4,000 a month&rdquo;</span>{" "}
          — and they get replaced as you go. Or{" "}
          <Link href="/intake" className="text-accent underline underline-offset-2">
            fill in a form instead
          </Link>
          .
        </p>
      ) : null}

      {/* Two columns because a conversation on its own gives no sense of how
          much is left to cover — the one thing the form genuinely did better. */}
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <ChatPanel
          profile={profile}
          months={months}
          messages={messages}
          onMessagesChange={setMessages}
          onProfileChange={setProfile}
          onResultChange={onResultChange}
        />

        <BudgetPanel profile={profile} result={result} />
      </div>
    </div>
  );
}
