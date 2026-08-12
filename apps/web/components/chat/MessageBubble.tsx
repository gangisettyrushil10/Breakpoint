import type { ChatMessage } from "@/lib/api/types";

export function MessageBubble({
  message,
  pending = false,
}: {
  message: ChatMessage;
  pending?: boolean;
}) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div className={`min-w-0 max-w-[85ch] ${isUser ? "" : "w-full"}`}>
        <div className="label mb-1.5">{isUser ? "You" : "BreakPoint"}</div>
        <div
          className={[
            "min-w-0 rounded-lg border px-4 py-3 text-[14.5px] leading-relaxed",
            isUser
              ? "border-line-strong bg-surface-2 text-ink"
              : "border-line bg-surface-1 text-ink",
            pending ? "text-ink-2" : "",
          ].join(" ")}
        >
          {/* Model output is plain prose — whitespace-pre-line keeps its
              paragraph breaks without rendering it as HTML. */}
          <p className="whitespace-pre-line">{message.content}</p>
        </div>
      </div>
    </div>
  );
}
