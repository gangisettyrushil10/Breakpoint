"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MessageBubble } from "@/components/chat/MessageBubble";
import { streamAgentMessage } from "@/lib/api/agent";
import type {
  ChatMessage,
  FinancialProfile,
  SimulateResponse,
  ToolCallRecord,
} from "@/lib/api/types";
import { money, months as fmtMonths } from "@/lib/format";

const STARTERS = [
  "How resilient is my budget right now?",
  "What would a layoff plus a car repair do to me?",
  "What single change moves my breaking point the most?",
];

const GUARDRAIL_NOTES = {
  regenerating: "Rewriting that — a figure wasn't grounded in the engine output.",
  withheld: "That reply was withheld — it stated figures the engine didn't produce.",
  blocked: "That reply was withheld and replaced.",
} as const;

/** What the agent is doing right now, for the pending bubble. */
type Phase = "thinking" | "running" | "writing";

const PHASE_LABEL: Record<Phase, string> = {
  thinking: "Thinking…",
  running: "Running the engine…",
  writing: "Writing the explanation…",
};

export function ChatPanel({
  profile,
  months = 6,
  messages,
  onMessagesChange,
  onProfileChange,
  onResultChange,
}: {
  /** The shared working profile. Controlled — this panel never owns it. */
  profile: FinancialProfile;
  months?: number;
  /** The shared transcript. Also controlled, so it persists across routes. */
  messages: ChatMessage[];
  onMessagesChange: (messages: ChatMessage[]) => void;
  /** Fires when the agent edited the profile via `patch_profile`. */
  onProfileChange: (profile: FinancialProfile) => void;
  /**
   * Fires with the run describing the user's real situation, so a sibling panel
   * can show a live score without issuing its own `/simulate` call.
   */
  onResultChange?: (result: SimulateResponse) => void;
}) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [phase, setPhase] = useState<Phase>("thinking");
  const [streamText, setStreamText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const [toolCalls, setToolCalls] = useState<ToolCallRecord[]>([]);
  const [guardrailNote, setGuardrailNote] = useState<string | null>(null);
  /** What the last turn cost. Shown so spend is visible, not a surprise. */
  const [usage, setUsage] = useState<{ tokens: number; calls: number } | null>(null);

  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, sending, streamText]);

  const send = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;

      // Send the transcript as it will be *after* this message — the server is
      // stateless and needs the whole thing.
      const next: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
      onMessagesChange(next);
      setInput("");
      setSending(true);
      setPhase("thinking");
      setStreamText("");
      setError(null);
      setGuardrailNote(null);
      setToolCalls([]);

      try {
        for await (const event of streamAgentMessage({
          messages: next,
          profile,
          months,
        })) {
          switch (event.type) {
            case "tool_call":
              setPhase("running");
              setToolCalls((prev) => [
                ...prev,
                { name: event.name, arguments: event.arguments, ok: event.ok },
              ]);
              break;

            case "simulate_run":
              // Which run describes the user's real situation is only settled at
              // the end; apply the same rule optimistically and let `done` win.
              if (!event.hasScenarios) {
                setResult(event.result);
                onResultChange?.(event.result);
              }
              break;

            case "profile":
              // The dashboard re-runs itself off the shared profile, so handing
              // the edit up is all that keeps the two views in agreement.
              onProfileChange(event.profile);
              break;

            case "sentence":
              setPhase("writing");
              setStreamText((prev) => prev + event.text);
              break;

            case "retract":
              // Clear, never append. A visible wrong figure with a correction
              // under it is the same failure with extra steps — and the clean
              // prefix was written to justify the sentence that failed.
              setStreamText("");
              break;

            case "notice":
              setGuardrailNote(GUARDRAIL_NOTES[event.kind]);
              break;

            case "done":
              // Authoritative. Everything streamed is discarded here, which is
              // what makes streaming unable to change the answer.
              onMessagesChange(event.response.messages);
              setToolCalls(event.response.toolCalls);
              if (event.response.simulateResult) {
                setResult(event.response.simulateResult);
                onResultChange?.(event.response.simulateResult);
              }
              setUsage({
                tokens: event.response.totalTokens,
                calls: event.response.modelCalls,
              });
              setStreamText("");
              break;

            case "error":
              throw new Error(event.detail);
          }
        }
      } catch (err) {
        // Roll the optimistic user turn back so retrying doesn't duplicate it.
        onMessagesChange(messages);
        setStreamText("");
        setInput(trimmed);
        setError(err instanceof Error ? err.message : "Something went wrong.");
      } finally {
        setSending(false);
      }
    },
    [
      messages,
      profile,
      months,
      sending,
      onMessagesChange,
      onProfileChange,
      onResultChange,
    ]
  );

  // One column, not two. This used to sit the raw engine output in a sticky
  // sidebar — which, once ChatSurface added the budget panel, made three columns
  // of figures competing for attention around a conversation. The raw output is
  // still one click away below; it is evidence, not the point.
  return (
    <div className="flex min-h-0 flex-col gap-4">
      <div className="flex min-h-0 min-w-0 flex-col gap-4">
        <div
          className="flex min-h-[52vh] flex-col gap-5"
          role="log"
          // Streaming into a live region makes a screen reader re-announce the
          // whole growing message on every append. Announce the finished reply
          // instead, once it lands in `messages`.
          aria-live={sending ? "off" : "polite"}
        >
          {messages.length === 0 && !sending ? (
            <EmptyState onPick={send} disabled={sending} />
          ) : null}

          {messages.map((message, i) => (
            <MessageBubble key={i} message={message} />
          ))}

          {sending ? (
            streamText ? (
              <MessageBubble message={{ role: "assistant", content: streamText }} />
            ) : (
              <MessageBubble
                message={{ role: "assistant", content: PHASE_LABEL[phase] }}
                pending
              />
            )
          ) : null}

          <div ref={endRef} />
        </div>

        {error ? (
          <p
            role="alert"
            className="rounded-lg border border-critical/40 bg-critical-dim px-4 py-3 text-[13px] text-critical"
          >
            {error}
          </p>
        ) : null}

        <form
          onSubmit={(event) => {
            event.preventDefault();
            void send(input);
          }}
          className="flex items-end gap-2 border-t border-line pt-4"
        >
          <label htmlFor="chat-input" className="sr-only">
            Ask about your financial resilience
          </label>
          <textarea
            id="chat-input"
            rows={2}
            value={input}
            disabled={sending}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void send(input);
              }
            }}
            placeholder="Ask what your budget can absorb…"
            className="min-w-0 flex-1 resize-none rounded-lg border border-line bg-surface-1 px-3.5 py-2.5 text-[15.5px] text-ink placeholder:text-ink-3 disabled:opacity-60"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="rounded-lg bg-accent px-4 py-2.5 text-[15px] font-medium text-bg disabled:cursor-not-allowed disabled:opacity-40"
          >
            {sending ? "…" : "Send"}
          </button>
        </form>
      </div>

      {/* Closed by default. Someone anxious about rent does not need a token
          count; someone checking whether the numbers are real does, and it is
          one click away for them. */}
      <details className="section-detail">
        <summary className="explain-summary text-[13px] text-ink-3">
          <span className="explain-word">Show the engine&rsquo;s raw output</span>
          <span aria-hidden className="explain-mark">
            +
          </span>
        </summary>
        <div className="mt-3">
          <EnginePanel
            result={result}
            toolCalls={toolCalls}
            note={guardrailNote}
            usage={usage}
          />
        </div>
      </details>
    </div>
  );
}

function EmptyState({
  onPick,
  disabled,
}: {
  onPick: (text: string) => void;
  disabled: boolean;
}) {
  return (
    <div className="rounded-lg border border-line bg-surface-1 p-5">
      <h2 className="text-[18px] font-semibold">Ask about your money situation</h2>
      <p className="mt-2 max-w-[58ch] text-[15px] leading-relaxed text-ink-2">
        Every number in a reply comes from the same deterministic engine behind the
        dashboard — the assistant runs it and explains the result, it never
        estimates.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {STARTERS.map((starter) => (
          <button
            key={starter}
            type="button"
            disabled={disabled}
            onClick={() => onPick(starter)}
            className="rounded-full border border-line bg-surface-2 px-3 py-1.5 text-[13.5px] text-ink-2 hover:border-line-strong hover:text-ink disabled:opacity-50"
          >
            {starter}
          </button>
        ))}
      </div>
    </div>
  );
}

/** Shows the raw tool output beside the prose, so the two can be compared. */
function EnginePanel({
  result,
  toolCalls,
  note,
  usage,
}: {
  result: SimulateResponse | null;
  toolCalls: ToolCallRecord[];
  note: string | null;
  usage: { tokens: number; calls: number } | null;
}) {
  return (
    <aside className="flex h-fit flex-col gap-4 rounded-lg border border-line bg-surface-1 p-4">
      <h2 className="label">Engine output</h2>

      {result ? (
        <dl className="flex flex-col gap-3.5">
          <Figure label="Resilience score" value={`${result.resilience.score}`} suffix="/ 100" />
          <Figure
            label="Runway"
            value={
              result.baseline.runwayMonths === null
                ? "—"
                : fmtMonths(result.baseline.runwayMonths)
            }
          />
          <Figure label="Monthly buffer" value={money(result.baseline.monthlyBufferCents)} />
          <Figure
            label="Breaking point"
            value={
              result.breakingPoint.triggered
                ? `Month ${(result.breakingPoint.monthIndex ?? 0) + 1}`
                : "Not triggered"
            }
            suffix={
              result.breakingPoint.triggered
                ? result.breakingPoint.shockCombination.join(" + ")
                : undefined
            }
          />
        </dl>
      ) : (
        <p className="text-[13px] leading-relaxed text-ink-3">
          Nothing run yet. Ask a question and the tool result lands here — these
          figures are what the reply is allowed to quote.
        </p>
      )}

      {toolCalls.length > 0 ? (
        <div className="border-t border-line pt-3">
          <h3 className="label mb-2">Tools called</h3>
          <ul className="flex flex-col gap-1.5">
            {toolCalls.map((call, i) => (
              <li key={i} className="flex items-center gap-2 text-[12px] text-ink-2">
                <span
                  aria-hidden
                  className={`size-1.5 shrink-0 rounded-full ${
                    call.ok ? "bg-stable" : "bg-critical"
                  }`}
                />
                <code className="tnum truncate">{call.name}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {note ? (
        <p className="border-t border-line pt-3 text-[12px] leading-relaxed text-caution">
          {note}
        </p>
      ) : null}

      {usage ? (
        <p className="border-t border-line pt-3 text-[11.5px] text-ink-3">
          Last turn:{" "}
          <span className="tnum">{usage.tokens.toLocaleString()}</span> tokens over{" "}
          <span className="tnum">{usage.calls}</span> model call
          {usage.calls === 1 ? "" : "s"}
        </p>
      ) : null}
    </aside>
  );
}

function Figure({
  label,
  value,
  suffix,
}: {
  label: string;
  value: string;
  suffix?: string;
}) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className="tnum mt-1 text-[15px]">
        {value}
        {suffix ? <span className="ml-1.5 text-[11.5px] text-ink-3">{suffix}</span> : null}
      </dd>
    </div>
  );
}
