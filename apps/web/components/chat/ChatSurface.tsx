"use client";

import Link from "next/link";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { useProfile } from "@/components/ProfileProvider";

/**
 * Client shim between the (server-rendered) chat page and the panel.
 *
 * Its only job is to hand `ChatPanel` the shared profile and transcript instead
 * of the hardcoded demo constants it used to receive, so a `patch_profile` edit
 * made here shows up on the dashboard and survives a refresh.
 */
export function ChatSurface() {
  const { profile, hasOwnProfile, setProfile, messages, setMessages, months, hydrated } =
    useProfile();

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
        <p className="rounded-lg border border-line bg-surface-1 px-4 py-3 text-[13px] text-ink-2">
          You&rsquo;re asking about the demo budget.{" "}
          <Link href="/intake" className="text-accent underline underline-offset-2">
            Enter your own numbers
          </Link>{" "}
          and every answer here will be about you instead.
        </p>
      ) : null}

      <ChatPanel
        profile={profile}
        months={months}
        messages={messages}
        onMessagesChange={setMessages}
        onProfileChange={setProfile}
      />
    </div>
  );
}
