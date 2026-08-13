"""The bounded model <-> tool loop.

The model is a router, not a calculator. It decides *which* simulation to run and
how to explain it; every number in the reply comes back from a tool.

Provider vocabulary lives in `provider.py` — this file deals only in `ModelTurn`
and `ToolCall`.

Two rules here are load-bearing and easy to regress:

* **Only a turn that asked for no tools can supply the reply.** Text that arrives
  alongside a tool call is a preamble ("Let me check that for you") and must
  never become the final answer.
* **A profile edit invalidates every simulation taken before it.** Those numbers
  describe a budget that no longer exists.
"""

import asyncio
import json
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, AsyncIterator, Protocol

from app.agent import guardrails
from app.agent.events import (
    AgentEvent,
    NoticeEvent,
    ProfileEvent,
    RetractEvent,
    SentenceEvent,
    SimulateRunEvent,
    WhatIfEvent,
    StartEvent,
    ToolCallEvent,
)
from app.agent.grounding import build_ledger
from app.agent.guardrails import SentenceGate
from app.agent.provider import ModelClient, ProviderError, ToolCall, tool_result_item
from app.agent.schemas import ChatMessage, GuardrailReport, ToolCallRecord
from app.agent.tools import commute_cost, registry, what_if
from app.domain.financial_profile import FinancialProfile
from app.routes.simulate import SimulateResponse

DEFAULT_MAX_ITERATIONS = 5
DEFAULT_TURN_BUDGET_SECONDS = 60.0
# Two identical failures means the model isn't recovering; stop rather than
# spending the remaining iterations on it.
MAX_CONSECUTIVE_TOOL_FAILURES = 2

NO_REPLY_FALLBACK = (
    "I wasn't able to put that together. Try asking again, and if it keeps "
    "happening the simulation service may be down."
)
REFUSAL_FALLBACK = (
    "I can't help with that one. I can explain what your budget can absorb and "
    "what would move your breaking point — ask me about either."
)
ITERATION_CAP_FALLBACK = (
    "I got partway through that and ran out of steps. Ask me for one thing at a "
    "time — for example, what a layoff alone would do — and I'll walk through it."
)
TRUNCATION_NOTICE = (
    "\n\n(I ran out of room mid-answer — ask me to continue and I'll pick up "
    "from there.)"
)
# Delivered as a user message, because that is the only channel available
# mid-turn — so it has to say explicitly that it is not from the person. Without
# that, the model reads it as the user objecting, apologises to them, and then
# recites every figure it has to prove it is complying. That is how a warm
# answer turns into a defensive data dump.
CORRECTION_REQUEST = (
    "[system check, not from the user] These figures were not in the tool "
    "output: {listed}. Write the answer again using only numbers the tools "
    "returned, or run the simulation that produces the one you need.\n\n"
    "Do not apologise, do not mention this correction, and do not tell the user "
    "anything was rewritten — they never saw the first attempt. Do not list "
    "every figure to prove yourself. Just answer their question, warmly and "
    "briefly, the way you would have if you had got it right first time."
)
FINALIZE_REQUEST = (
    "You're out of tool calls for this turn. Answer now using only what the "
    "tools have already returned."
)


class AgentError(RuntimeError):
    """Raised when a turn cannot be completed. The route maps this to a status."""

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail or message


class TurnSink(Protocol):
    """Where a streaming turn puts its progress. `None` means non-streaming.

    Threading an optional sink is deliberate — the alternative, reimplementing
    `run()` by draining `stream()`, would make the path covered by the whole
    existing suite depend on the new uncovered one, force a second fake into
    every scripted-model test, and require smuggling the result out through a
    terminal event because async generators cannot return values.
    """

    async def emit(self, event: AgentEvent) -> None: ...


@dataclass
class AgentRunResult:
    reply: str
    profile: FinancialProfile
    #: The run the dashboard should show — the unstressed one where available.
    simulate_result: SimulateResponse | None = None
    #: Every simulation this turn, in call order.
    simulate_runs: list[SimulateResponse] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    guardrail: GuardrailReport = field(default_factory=GuardrailReport)
    stop_reason: str = "completed"
    #: What the turn cost, summed across every model call it made.
    total_tokens: int = 0
    model_calls: int = 0


@dataclass
class _TurnState:
    """Everything that changes while a single chat turn runs."""

    conversation: list[Any]
    profile: FinancialProfile
    user_messages: list[str]
    tool_defaults: dict[str, dict]
    deadline: float
    simulate_runs: list[tuple[dict, SimulateResponse]] = field(default_factory=list)
    #: Web-backed cost estimates made this turn. Deliberately NOT cleared when
    #: the profile is edited: the usual sequence is estimate → user agrees →
    #: patch_profile → reply, and clearing would strip the ledger of the very
    #: figure the confirming reply has to quote.
    lookup_results: list[dict] = field(default_factory=list)
    #: Hypothetical comparisons made this turn. Like lookups, kept across a
    #: profile edit: someone may try a change, like it, and save it, and the
    #: reply confirming that still needs to quote the figures that persuaded them.
    what_if_results: list[dict] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    final_text: str = ""
    stop_reason: str = "completed"
    #: Every model call this turn, summed. The transcript is resent on each
    #: iteration, so this is the real cost of the turn — not the reply length.
    total_tokens: int = 0
    model_calls: int = 0

    def remaining(self) -> float:
        return self.deadline - monotonic()

    def has_budget(self, need: float = 2.0) -> bool:
        return self.remaining() > need

    @property
    def results(self) -> list[SimulateResponse]:
        return [result for _, result in self.simulate_runs]

    def dashboard_result(self) -> SimulateResponse | None:
        """The run that describes the user's actual situation.

        A turn may simulate several scenarios ("compare a layoff to today"). The
        dashboard must not be handed a hypothetical stress run labelled as the
        current state, so prefer the most recent scenario-free run.
        """
        for arguments, result in reversed(self.simulate_runs):
            if not arguments.get("scenarios"):
                return result
        return self.simulate_runs[0][1] if self.simulate_runs else None

    def ledger(self):
        return build_ledger(
            simulate_results=self.results,
            tool_arguments=[call.arguments for call in self.tool_calls],
            user_messages=self.user_messages,
            lookup_results=self.lookup_results,
            what_if_results=self.what_if_results,
        )


class AgentLoop:
    """Runs one chat turn to completion.

    `client` is injected so tests drive the loop with a scripted model; it only
    needs the `ModelClient` protocol from `provider.py`.
    """

    def __init__(
        self,
        client: ModelClient,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        turn_budget_seconds: float = DEFAULT_TURN_BUDGET_SECONDS,
        stream_answer_turn: bool = False,
    ) -> None:
        self.client = client
        self.max_iterations = max_iterations
        self.turn_budget_seconds = turn_budget_seconds
        # Off by default because it costs one extra generation per turn — see
        # `_stream_answer`. The prose still arrives sentence-by-sentence without
        # it; this only changes *when* generation and display overlap.
        self.stream_answer_turn = stream_answer_turn

    def _can_stream(self) -> bool:
        return hasattr(self.client, "create_streaming")

    async def run(
        self,
        messages: list[ChatMessage],
        profile: FinancialProfile,
        months: int = 6,
    ) -> AgentRunResult:
        """Run one turn to completion. Unchanged behaviour — no sink, no events."""
        return await self._run(messages, profile, months, sink=None)

    async def stream(
        self,
        messages: list[ChatMessage],
        profile: FinancialProfile,
        months: int = 6,
    ) -> AsyncIterator[AgentEvent | AgentRunResult]:
        """Same turn, reporting progress as it goes.

        Yields `AgentEvent`s and then, as the final item, the `AgentRunResult` —
        which is byte-identical to what `run()` would have returned for the same
        script. Streaming is progressive disclosure; it never changes the answer.
        """
        queue: asyncio.Queue[object] = asyncio.Queue()
        done = object()

        class _QueueSink:
            async def emit(self, event: AgentEvent) -> None:
                await queue.put(event)

        async def produce() -> AgentRunResult:
            try:
                return await self._run(messages, profile, months, sink=_QueueSink())
            finally:
                # Unbounded queue on purpose: a bounded one deadlocks here if the
                # consumer has gone away, and a turn only produces tens of events.
                queue.put_nowait(done)

        task = asyncio.create_task(produce())
        try:
            while (item := await queue.get()) is not done:
                yield item  # type: ignore[misc]
            # Re-raises AgentError, which the route turns into a 502 when it
            # happens before the commit point.
            yield await task
        finally:
            # A closed browser tab must not leave a model call running and
            # billing. Starlette closes the generator on disconnect.
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def _run(
        self,
        messages: list[ChatMessage],
        profile: FinancialProfile,
        months: int,
        sink: TurnSink | None,
    ) -> AgentRunResult:
        state = _TurnState(
            conversation=[
                {"role": message.role, "content": message.content}
                for message in messages
            ],
            profile=profile,
            user_messages=[m.content for m in messages if m.role == "user"],
            # The horizon the dashboard is showing becomes the tool's default,
            # so the model needn't guess it and it stays out of the (cached,
            # frozen) system prompt.
            tool_defaults={"simulate": {"months": months}},
            deadline=monotonic() + self.turn_budget_seconds,
        )

        await self._converse(state, sink)

        # Release the prose sentence by sentence before the final review runs.
        # The gate can only ever be as strict as `review_output`, so anything it
        # lets through is text the authority below would also have allowed.
        released_clean = True
        if sink is not None:
            if self.stream_answer_turn and self._can_stream() and state.has_budget():
                released_clean = await self._stream_answer(state, sink)
            else:
                released_clean = await self._emit_reply(state, sink)

        verdict, regenerated = await self._review(state, sink)

        # Retract when what was streamed is no longer what the reply says. The
        # clean prefix is not innocent in that case — it was written to justify
        # the sentence that failed — so the bubble is cleared, never appended to.
        if sink is not None and (not released_clean or verdict.blocked or regenerated):
            await sink.emit(RetractEvent(reason="; ".join(verdict.reasons) or "revised"))

        return AgentRunResult(
            reply=verdict.text,
            profile=state.profile,
            simulate_result=state.dashboard_result(),
            simulate_runs=state.results,
            tool_calls=state.tool_calls,
            guardrail=GuardrailReport(
                blocked=verdict.blocked,
                regenerated=regenerated,
                unsupported=verdict.unsupported,
                reasons=verdict.reasons,
            ),
            stop_reason=state.stop_reason,
            total_tokens=state.total_tokens,
            model_calls=state.model_calls,
        )

    # -- review -----------------------------------------------------------

    async def _review(
        self, state: _TurnState, sink: TurnSink | None
    ) -> tuple[guardrails.GuardrailVerdict, bool]:
        """The authority on what the reply is. Shared by both entry points."""
        verdict = guardrails.review_output(state.final_text, state.ledger())
        regenerated = False

        if verdict.regenerate_requested and state.has_budget():
            if sink is not None:
                await sink.emit(
                    NoticeEvent(
                        kind="regenerating",
                        detail="; ".join(verdict.reasons),
                    )
                )
            regenerated = await self._regenerate(state, verdict.unsupported)
            verdict = guardrails.review_output(
                state.final_text, state.ledger(), allow_regeneration=False
            )
        elif verdict.regenerate_requested:
            verdict = guardrails.review_output(
                state.final_text, state.ledger(), allow_regeneration=False
            )

        if sink is not None and verdict.blocked:
            await sink.emit(
                NoticeEvent(
                    kind="withheld" if verdict.unsupported else "blocked",
                    detail="; ".join(verdict.reasons),
                )
            )

        return verdict, regenerated

    async def _stream_answer(self, state: _TurnState, sink: TurnSink) -> bool:
        """Regenerate the answer as a streamed, provably-terminal call.

        Why this costs an extra generation, and why there is no cheaper way:
        the API emits a turn's text *before* any `function_call` item, so
        "this turn is the answer and not a tool preamble" is only knowable after
        all its text has arrived. Speculatively streaming and retracting is not
        an option — preamble text can invent figures against an empty ledger,
        which is the exact failure the grounding ledger exists to prevent.

        `tool_choice="none"` makes terminality a precondition rather than a
        discovery, so this call can be streamed safely. On any failure it falls
        back to replaying the text already in hand, so the turn still completes.
        """
        gate = SentenceGate(state.ledger())
        clean = True

        async def on_delta(delta: str) -> None:
            nonlocal clean
            if not clean:
                return  # Stop emitting; generation continues (see below).
            for verdict in gate.feed(delta):
                if not verdict.ok:
                    clean = False
                    return
                if verdict.text or verdict.separator:
                    await sink.emit(SentenceEvent(text=verdict.text + verdict.separator))

        state.conversation.append({"role": "user", "content": FINALIZE_REQUEST})
        try:
            turn = await self._create(
                state, tool_choice="none", on_text_delta=on_delta
            )
        except AgentError:
            # Nothing streamed is lost — fall back to replaying what we have.
            return await self._emit_reply(state, sink)

        if not turn.text:
            return await self._emit_reply(state, sink)

        state.final_text = turn.text

        if clean:
            for verdict in gate.flush():
                if not verdict.ok:
                    return False
                if verdict.text or verdict.separator:
                    await sink.emit(SentenceEvent(text=verdict.text + verdict.separator))

        return clean

    async def _emit_reply(self, state: _TurnState, sink: TurnSink) -> bool:
        """Release the reply one gate-cleared sentence at a time.

        Returns whether the whole thing cleared. On the first failure it stops
        emitting — but generation has already finished, so nothing is truncated:
        `_regenerate` still gets the complete assistant turn to rewrite, which is
        strictly better context than a half-sentence.
        """
        gate = SentenceGate(state.ledger())
        verdicts = [*gate.feed(state.final_text), *gate.flush()]

        for verdict in verdicts:
            if not verdict.ok:
                return False
            if verdict.text or verdict.separator:
                await sink.emit(SentenceEvent(text=verdict.text + verdict.separator))

        return True

    # -- the loop ---------------------------------------------------------

    async def _converse(self, state: _TurnState, sink: TurnSink | None = None) -> None:
        consecutive_failures = 0
        started = False

        for _ in range(self.max_iterations):
            if not state.has_budget():
                state.stop_reason = "budget_exhausted"
                break

            turn = await self._create(state)

            # The commit point: the first provider call succeeded, so the route
            # can stop holding open its chance to return a clean 502.
            if sink is not None and not started:
                started = True
                await sink.emit(
                    StartEvent(months=state.tool_defaults["simulate"]["months"])
                )

            if turn.refusal:
                state.final_text = REFUSAL_FALLBACK
                state.stop_reason = "refusal"
                return

            if not turn.wants_tools:
                # Terminal turn — the only kind whose text may be the answer.
                state.final_text = turn.text
                if turn.incomplete:
                    state.stop_reason = "truncated"
                    if turn.text:
                        state.final_text = turn.text + TRUNCATION_NOTICE
                else:
                    state.stop_reason = "completed"
                return

            state.conversation.extend(turn.raw_items)
            failed = await self._run_tools(state, turn.tool_calls, sink)
            consecutive_failures = consecutive_failures + 1 if failed else 0

            if consecutive_failures >= MAX_CONSECUTIVE_TOOL_FAILURES:
                state.stop_reason = "tool_failures"
                break
        else:
            state.stop_reason = "max_iterations"

        # The loop ran out of room. Give the model one chance to answer from
        # what it already has rather than showing a preamble or a canned line.
        if state.has_budget():
            await self._finalize(state)

        if not state.final_text:
            state.final_text = (
                ITERATION_CAP_FALLBACK
                if state.stop_reason in {"max_iterations", "budget_exhausted"}
                else NO_REPLY_FALLBACK
            )

    async def _finalize(self, state: _TurnState) -> None:
        state.conversation.append({"role": "user", "content": FINALIZE_REQUEST})
        try:
            turn = await self._create(state, tool_choice="none")
        except AgentError:
            return
        if turn.text:
            state.final_text = turn.text

    async def _regenerate(self, state: _TurnState, unsupported: list[str]) -> bool:
        """Ask once for a rewrite grounded in what the tools returned."""
        state.conversation.append(
            {"role": "assistant", "content": state.final_text}
        )
        state.conversation.append(
            {
                "role": "user",
                "content": CORRECTION_REQUEST.format(listed=", ".join(unsupported)),
            }
        )
        try:
            turn = await self._create(state, tool_choice="none")
        except AgentError:
            return False
        if turn.text:
            state.final_text = turn.text
            return True
        return False

    # -- tools ------------------------------------------------------------

    async def _run_tools(
        self, state: _TurnState, calls: list[ToolCall], sink: TurnSink | None = None
    ) -> bool:
        """Execute every requested tool. Returns True if all of them failed."""
        if not calls:
            return False

        failures = 0
        for call in calls:
            if call.parse_error:
                payload = {
                    "ok": False,
                    "error": "invalid_arguments_json",
                    "detail": call.parse_error,
                }
                arguments: dict = {}
            else:
                arguments = {
                    **state.tool_defaults.get(call.name, {}),
                    **call.arguments,
                }
                payload = registry.dispatch(call.name, state.profile, arguments)

            ok = bool(payload.get("ok"))
            failures += not ok
            state.tool_calls.append(
                ToolCallRecord(name=call.name, arguments=arguments, ok=ok)
            )
            # The call is announced before its results, so the UI reads in the
            # order things actually happened.
            if sink is not None:
                await sink.emit(
                    ToolCallEvent(name=call.name, arguments=arguments, ok=ok)
                )

            if ok:
                await self._absorb(state, call.name, arguments, payload, sink)

            state.conversation.append(
                tool_result_item(
                    call.call_id, json.dumps(payload, separators=(",", ":"))
                )
            )

        return failures == len(calls)

    async def _absorb(
        self,
        state: _TurnState,
        name: str,
        arguments: dict,
        payload: dict,
        sink: TurnSink | None = None,
    ) -> None:
        tool = registry.get(name)

        if tool is not None and tool.mutates_profile:
            state.profile = FinancialProfile.model_validate(payload["profile"])
            # Every simulation so far described the pre-edit budget. Keeping
            # them would let the guardrail bless post-edit figures against
            # stale numbers.
            state.simulate_runs.clear()
            if sink is not None:
                await sink.emit(ProfileEvent(profile=state.profile.model_dump()))

        if name == commute_cost.TOOL_NAME:
            state.lookup_results.append(payload)

        if name == what_if.TOOL_NAME:
            state.what_if_results.append(payload)
            if sink is not None:
                await sink.emit(
                    WhatIfEvent(
                        scoreBefore=payload["score"]["before"],
                        scoreAfter=payload["score"]["after"],
                        changed=payload.get("changed", []),
                    )
                )

        if name == "simulate":
            result = SimulateResponse.model_validate(payload["result"])
            state.simulate_runs.append((arguments, result))
            if sink is not None:
                await sink.emit(
                    SimulateRunEvent(
                        index=len(state.simulate_runs) - 1,
                        hasScenarios=bool(arguments.get("scenarios")),
                        result=result.model_dump(),
                    )
                )

    # -- provider ---------------------------------------------------------

    async def _create(
        self,
        state: _TurnState,
        tool_choice: str | None = None,
        on_text_delta=None,
    ):
        try:
            if on_text_delta is not None and self._can_stream():
                turn = await self.client.create_streaming(  # type: ignore[attr-defined]
                    state.conversation,
                    tool_choice=tool_choice,
                    timeout=max(1.0, state.remaining()),
                    on_text_delta=on_text_delta,
                )
            else:
                turn = await self.client.create(
                    state.conversation,
                    tool_choice=tool_choice,
                    timeout=max(1.0, state.remaining()),
                )
        except ProviderError as error:
            raise AgentError(str(error), detail=error.detail) from error
        except Exception as error:  # noqa: BLE001 — surfaced as a 502 upstream
            raise AgentError(
                "The model service is unavailable. Please try again.",
                detail=f"{type(error).__name__}: {error}",
            ) from error

        # Metered here so no call path can forget to count itself.
        state.model_calls += 1
        state.total_tokens += turn.total_tokens
        return turn
