import { API_URL, ApiError } from "./client";
import type { AgentEvent, ChatRequest, ChatResponse } from "./types";

/**
 * One chat turn. The agent is stateless — send the whole transcript and the
 * working profile every time, and use the profile that comes back (the agent
 * may have edited it via its `patch_profile` tool).
 */
export async function sendAgentMessage(
  request: ChatRequest,
  options: { signal?: AbortSignal } = {}
): Promise<ChatResponse> {
  const response = await fetch(`${API_URL}/agent/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: options.signal,
  });

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    const detail =
      typeof body === "object" && body && "detail" in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(`Chat failed: ${detail}`, response.status, body);
  }

  return body as ChatResponse;
}

/**
 * The same turn, narrated over SSE.
 *
 * Hand-rolled rather than `EventSource`, which is GET-only — the body here is
 * the whole transcript plus the profile, up to 24KB. That rules out the browser
 * primitive entirely, and the parsing it would have done is ~30 lines.
 *
 * Consume it as an async iterator; `done` is always the last event unless
 * `error` is. Both are terminal, so a `for await` over this always ends.
 */
export async function* streamAgentMessage(
  request: ChatRequest,
  options: { signal?: AbortSignal } = {}
): AsyncGenerator<AgentEvent> {
  const response = await fetch(`${API_URL}/agent/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: options.signal,
  });

  if (!response.ok) {
    // Validation, rate limiting and a dead provider on the opening call all
    // still arrive as ordinary JSON status codes — the server commits to the
    // stream only once it has something real to say.
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    const detail =
      typeof body === "object" && body && "detail" in body
        ? JSON.stringify((body as { detail: unknown }).detail)
        : response.statusText;
    throw new ApiError(`Chat failed: ${detail}`, response.status, body);
  }

  if (!response.body) {
    throw new ApiError("Streaming is not supported here.", 500, null);
  }

  const reader = response.body.getReader();
  // `stream: true` matters — a multibyte character split across two chunks
  // decodes to garbage without it.
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      let split = buffer.indexOf("\n\n");
      while (split !== -1) {
        const frame = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);

        const event = parseFrame(frame);
        if (event) yield event;

        split = buffer.indexOf("\n\n");
      }
    }
  } finally {
    // Tell the server to stop generating if the caller bailed out early.
    reader.cancel().catch(() => {});
  }
}

function parseFrame(frame: string): AgentEvent | null {
  // `: ping` keepalives carry no data.
  if (!frame.trim() || frame.startsWith(":")) return null;

  let name = "";
  let data = "";
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) name = line.slice(7);
    else if (line.startsWith("data: ")) data = line.slice(6);
  }
  if (!name || !data) return null;

  try {
    return { type: name, ...JSON.parse(data) } as AgentEvent;
  } catch {
    return null;
  }
}
