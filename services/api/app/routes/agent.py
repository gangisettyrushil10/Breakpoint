"""POST /agent/chat and /agent/chat/stream — validate, run the loop, return.

Deliberately thin. All behaviour lives in `app.agent.*`; this file maps between
HTTP and the loop, and turns failures into status codes.

The routes are `async` on purpose: a sync route runs in the anyio threadpool
(40 slots by default), so a handful of slow model calls would starve
`/simulate` and `/health` along with it.

The two endpoints answer the same question and return the same
`ChatResponse` — the streaming one just narrates itself on the way. Keeping the
non-streaming route byte-identical means the existing contract and its tests
stay frozen, and gives the client a fallback that needs no server support.
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.agent.loop import AgentError, AgentLoop, AgentRunResult
from app.agent.provider import ConfigError, OpenAIModelClient, build_client
from app.agent.ratelimit import enforce_rate_limit
from app.agent.schemas import ChatMessage, ChatRequest, ChatResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agent"])

UPSTREAM_FAILURE = "The model service is unavailable. Please try again."

#: Proxies drop connections that go quiet, and a model call can outlast their
#: patience. A comment frame keeps the pipe warm without meaning anything.
KEEPALIVE_SECONDS = 15.0


def get_agent_loop(request: Request) -> AgentLoop:
    """Overridable in tests via `app.dependency_overrides`.

    The HTTP client is built once at startup and shared; constructing one per
    request would mean a fresh connection pool and TLS handshake every turn.
    """
    client = getattr(request.app.state, "openai_client", None)
    if client is None:
        try:
            client = build_client()
        except ConfigError as error:
            # Server misconfiguration, no user data in the message — safe and
            # genuinely useful to return.
            raise HTTPException(status_code=502, detail=str(error)) from error
        request.app.state.openai_client = client

    return AgentLoop(
        client=OpenAIModelClient(client),
        # Opt-in: token-streaming the answer costs one extra generation per turn,
        # because a turn is only known to be terminal after its text has already
        # arrived. Off, the prose still streams — just sentence-at-a-time once
        # generation finishes.
        stream_answer_turn=os.environ.get("STREAM_ANSWER_TURN") == "1",
    )


def _log_turn(result: AgentRunResult, streamed: bool) -> None:
    """One line per turn: what it did, why it stopped, what it cost.

    `stop_reason` already distinguishes the interesting failures
    (`max_iterations`, `budget_exhausted`, `tool_failures`, `refusal`,
    `truncated`) and nothing was reading it. Never logs profile figures or reply
    text — this is an operational record, not a transcript.
    """
    logger.info(
        "agent turn: stop=%s streamed=%s model_calls=%d tokens=%d tools=%s "
        "blocked=%s regenerated=%s",
        result.stop_reason,
        streamed,
        result.model_calls,
        result.total_tokens,
        ",".join(f"{c.name}{'' if c.ok else '!'}" for c in result.tool_calls) or "-",
        result.guardrail.blocked,
        result.guardrail.regenerated,
    )


def _chat_response(request: ChatRequest, result: AgentRunResult) -> ChatResponse:
    """Shared by both endpoints so the streamed `done` frame cannot drift."""
    return ChatResponse(
        messages=[*request.messages, ChatMessage(role="assistant", content=result.reply)],
        reply=result.reply,
        profile=result.profile,
        simulateResult=result.simulate_result,
        simulateRuns=result.simulate_runs,
        toolCalls=result.tool_calls,
        guardrail=result.guardrail,
        stopReason=result.stop_reason,
        totalTokens=result.total_tokens,
        modelCalls=result.model_calls,
    )


def _require_user_last(request: ChatRequest) -> None:
    if request.messages[-1].role != "user":
        raise HTTPException(
            status_code=422,
            detail="The last message must be from the user.",
        )


def _frame(event: str, payload: dict) -> str:
    """One SSE frame. `json.dumps` escapes newlines, so `data:` stays one line."""
    return f"event: {event}\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"


@router.post("/agent/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    loop: AgentLoop = Depends(get_agent_loop),
    _: None = Depends(enforce_rate_limit),
) -> ChatResponse:
    _require_user_last(request)

    try:
        result = await loop.run(
            messages=request.messages,
            profile=request.profile,
            months=request.months,
        )
    except AgentError as error:
        # The provider's own error text can carry request ids, org detail, and
        # echoed request fragments. Log it; never return it.
        logger.warning("agent turn failed: %s", error.detail)
        raise HTTPException(status_code=502, detail=UPSTREAM_FAILURE) from error

    _log_turn(result, streamed=False)
    return _chat_response(request, result)


@router.post("/agent/chat/stream")
async def chat_stream(
    request: ChatRequest,
    loop: AgentLoop = Depends(get_agent_loop),
    _: None = Depends(enforce_rate_limit),
) -> StreamingResponse:
    """The same turn as `/agent/chat`, narrated over SSE.

    Dependencies and validation run before a single byte is written, so the 429,
    the missing-key 502, and the 422s are all still ordinary JSON responses.

    The subtle case is a provider failure. Once headers are sent there is no
    status code left to change, so the first event is pulled *eagerly* here:
    `stream()` emits `start` only after the opening model call succeeds, which
    means a failure on that call still surfaces as an honest 502 with nothing
    leaked. Failures after that become an `error` frame on a 200 the client has
    already committed to — which is the honest thing to do, because by then the
    tool results really have been delivered.
    """
    _require_user_last(request)

    events = loop.stream(
        messages=request.messages,
        profile=request.profile,
        months=request.months,
    )

    try:
        first = await events.__anext__()
    except AgentError as error:
        await events.aclose()
        logger.warning("agent stream failed before commit: %s", error.detail)
        raise HTTPException(status_code=502, detail=UPSTREAM_FAILURE) from error
    except StopAsyncIteration:  # pragma: no cover — stream always emits or raises
        await events.aclose()
        raise HTTPException(status_code=502, detail=UPSTREAM_FAILURE) from None

    return StreamingResponse(
        _frames(request, first, events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # nginx and friends buffer text/event-stream by default.
            "X-Accel-Buffering": "no",
        },
    )


async def _frames(
    request: ChatRequest, first: object, events: AsyncIterator
) -> AsyncIterator[str]:
    """Serialise the event stream, always terminating with `done` or `error`.

    Every exit path yields a terminator, because a client looping until one of
    those two frames would otherwise hang forever. Note the terminator is never
    emitted from a `finally`: on client disconnect Starlette closes this
    generator, and yielding while unwinding a `GeneratorExit` raises
    "async generator ignored GeneratorExit".
    """

    def render(item: object) -> str:
        payload = asdict(item)  # type: ignore[arg-type]
        return _frame(payload.pop("type"), payload)

    try:
        yield render(first)

        while True:
            try:
                item = await asyncio.wait_for(
                    events.__anext__(), timeout=KEEPALIVE_SECONDS
                )
            except TimeoutError:
                yield ": ping\n\n"
                continue
            except StopAsyncIteration:
                # The loop ended without handing back a result. Shouldn't happen,
                # but the client still needs to be let go.
                yield _frame("error", {"detail": UPSTREAM_FAILURE})
                return

            if isinstance(item, AgentRunResult):
                _log_turn(item, streamed=True)
                # Nested under `response` so the frame is self-describing and the
                # client can hand it straight to the same code path that handles
                # a non-streaming reply.
                yield _frame(
                    "done",
                    {"response": _chat_response(request, item).model_dump(mode="json")},
                )
                return

            yield render(item)

    except AgentError as error:
        logger.warning("agent stream failed after commit: %s", error.detail)
        yield _frame("error", {"detail": UPSTREAM_FAILURE})
    except Exception as error:  # noqa: BLE001 — never leave the client hanging
        logger.exception("agent stream crashed: %s", error)
        yield _frame("error", {"detail": UPSTREAM_FAILURE})
    finally:
        await events.aclose()
