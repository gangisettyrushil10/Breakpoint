"""Streaming must be progressive disclosure and nothing more.

The load-bearing test here is the equivalence harness: every script from
`test_agent_loop.py` is replayed through both `run()` and `stream()`, and the
terminal `AgentRunResult`s must be equal. If that holds, streaming cannot change
what the user ends up reading — it only changes when they start reading it.

The rest of the file defends the property that makes streaming safe at all:
**no unsafe or ungrounded text ever reaches a `sentence` frame.**
"""

import asyncio

import pytest
from test_agent_loop import (
    ExplodingModel,
    ScriptedModel,
    call_tool,
    preamble_then_call,
    refuse,
    say,
    truncated,
    user,
)
from test_agent_tools import maya_profile

from app.agent.events import (
    NoticeEvent,
    ProfileEvent,
    RetractEvent,
    SentenceEvent,
    SimulateRunEvent,
    StartEvent,
    ToolCallEvent,
)
from app.agent.loop import AgentError, AgentLoop, AgentRunResult
from app.agent.provider import OpenAIModelClient


def collect(model: ScriptedModel, messages, profile, **kwargs):
    """Drain `stream()`, splitting events from the terminal result."""
    loop = AgentLoop(client=OpenAIModelClient(model), **kwargs)

    async def go():
        events, result = [], None
        async for item in loop.stream(messages, profile):
            if isinstance(item, AgentRunResult):
                result = item
            else:
                events.append(item)
        return events, result

    return asyncio.run(go())


def run_only(model: ScriptedModel, messages, profile, **kwargs):
    loop = AgentLoop(client=OpenAIModelClient(model), **kwargs)
    return asyncio.run(loop.run(messages, profile))


def sentences(events) -> str:
    return "".join(e.text for e in events if isinstance(e, SentenceEvent))


# --------------------------------------------------------------------------
# Equivalence: stream() and run() must agree on the answer
# --------------------------------------------------------------------------

SCRIPTS = {
    "plain_answer": [say("Your budget holds up.")],
    "tool_then_answer": [
        call_tool("simulate", {"scenarios": []}),
        say("The engine found no breaking point."),
    ],
    "preamble_is_discarded": [
        preamble_then_call("Let me check that.", "simulate", {"scenarios": []}),
        say("No breaking point in this window."),
    ],
    "refusal": [refuse()],
    "truncated": [truncated("Your runway is")],
    "blocked_advice": [
        call_tool("simulate", {"scenarios": []}),
        say("You should take out a payday loan."),
    ],
    "ungrounded_then_regenerated": [
        call_tool("simulate", {"scenarios": []}),
        say("Your runway is 47.5 months."),
        say("The engine found no breaking point."),
    ],
    "profile_edit": [
        call_tool("patch_profile", {"expenses": {"rentCents": 180_000}}),
        say("Updated."),
    ],
}


@pytest.mark.parametrize("name", sorted(SCRIPTS))
def test_stream_and_run_produce_the_same_result(name: str) -> None:
    script = SCRIPTS[name]

    streamed_events, streamed = collect(
        ScriptedModel(list(script)), user("Tell me"), maya_profile()
    )
    plain = run_only(ScriptedModel(list(script)), user("Tell me"), maya_profile())

    assert streamed is not None
    assert streamed.reply == plain.reply
    assert streamed.stop_reason == plain.stop_reason
    assert streamed.guardrail == plain.guardrail
    assert streamed.profile == plain.profile
    assert [c.model_dump() for c in streamed.tool_calls] == [
        c.model_dump() for c in plain.tool_calls
    ]
    assert streamed.simulate_result == plain.simulate_result
    # And streaming actually happened.
    assert any(isinstance(e, StartEvent) for e in streamed_events)


# --------------------------------------------------------------------------
# The safety property
# --------------------------------------------------------------------------


def test_a_blocked_recommendation_never_reaches_a_sentence_frame() -> None:
    events, result = collect(
        ScriptedModel(
            [
                call_tool("simulate", {"scenarios": []}),
                say("You should take out a payday loan to cover the gap."),
            ]
        ),
        user("What should I do?"),
        maya_profile(),
    )

    assert "payday" not in sentences(events).lower()
    assert result.guardrail.blocked is True
    assert any(isinstance(e, NoticeEvent) for e in events)


def test_an_ungrounded_figure_never_reaches_a_sentence_frame() -> None:
    events, _ = collect(
        ScriptedModel(
            [
                call_tool("simulate", {"scenarios": []}),
                say("Your runway is 47.5 months, which is comfortable."),
                say("The engine found no breaking point."),
            ]
        ),
        user("How am I doing?"),
        maya_profile(),
    )

    assert "47.5" not in sentences(events)


def test_preamble_text_never_reaches_a_sentence_frame() -> None:
    """Text alongside a tool call is a preamble, and may invent numbers."""
    events, _ = collect(
        ScriptedModel(
            [
                preamble_then_call(
                    "I think your score is around 91.", "simulate", {"scenarios": []}
                ),
                say("The engine found no breaking point."),
            ]
        ),
        user("How am I doing?"),
        maya_profile(),
    )

    streamed = sentences(events)
    assert "91" not in streamed
    assert "I think" not in streamed


def test_a_failed_sentence_produces_a_retract_before_anything_else() -> None:
    events, _ = collect(
        ScriptedModel(
            [
                call_tool("simulate", {"scenarios": []}),
                say("Your buffer is fine. Your runway is 47.5 months."),
                say("The engine found no breaking point."),
            ]
        ),
        user("How am I doing?"),
        maya_profile(),
    )

    kinds = [type(e) for e in events]
    assert RetractEvent in kinds

    retract_at = kinds.index(RetractEvent)
    # The clean prefix went out, then was withdrawn — never appended to.
    assert any(k is SentenceEvent for k in kinds[:retract_at])


def test_a_clean_reply_is_not_retracted() -> None:
    events, result = collect(
        ScriptedModel(
            [
                call_tool("simulate", {"scenarios": []}),
                say("The engine found no breaking point in this window."),
            ]
        ),
        user("How am I doing?"),
        maya_profile(),
    )

    assert not any(isinstance(e, RetractEvent) for e in events)
    assert "no breaking point" in sentences(events)
    assert result.guardrail.blocked is False


# --------------------------------------------------------------------------
# Structural events
# --------------------------------------------------------------------------


def test_tool_and_simulate_events_arrive_before_the_prose() -> None:
    events, _ = collect(
        ScriptedModel(
            [
                call_tool("simulate", {"scenarios": []}),
                say("The engine found no breaking point."),
            ]
        ),
        user("Run it"),
        maya_profile(),
    )

    kinds = [type(e) for e in events]
    assert kinds.index(ToolCallEvent) < kinds.index(SentenceEvent)
    assert kinds.index(SimulateRunEvent) < kinds.index(SentenceEvent)
    # A call is announced before the result it produced.
    assert kinds.index(ToolCallEvent) < kinds.index(SimulateRunEvent)


def test_a_scenario_free_run_is_flagged_for_the_dashboard() -> None:
    events, _ = collect(
        ScriptedModel(
            [
                call_tool("simulate", {"scenarios": []}),
                say("No breaking point."),
            ]
        ),
        user("Run it"),
        maya_profile(),
    )

    runs = [e for e in events if isinstance(e, SimulateRunEvent)]
    assert [r.hasScenarios for r in runs] == [False]


def test_a_profile_edit_emits_the_new_profile() -> None:
    events, result = collect(
        ScriptedModel(
            [
                call_tool("patch_profile", {"expenses": {"rentCents": 180_000}}),
                say("Updated your rent."),
            ]
        ),
        user("My rent is $1,800 now"),
        maya_profile(),
    )

    edits = [e for e in events if isinstance(e, ProfileEvent)]
    assert len(edits) == 1
    assert edits[0].profile["expenses"]["rentCents"] == 180_000
    assert result.profile.expenses.rentCents == 180_000


def test_start_carries_the_server_horizon() -> None:
    events, _ = collect(
        ScriptedModel([say("Hello.")]), user("Hi"), maya_profile()
    )

    start = next(e for e in events if isinstance(e, StartEvent))
    assert start.months == 6


# --------------------------------------------------------------------------
# Failure before the commit point
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Answer-turn token streaming (stream_answer_turn=True)
# --------------------------------------------------------------------------


class StreamingScriptedModel(ScriptedModel):
    """A scripted model that can also hand back text in deltas.

    Mirrors what `OpenAIModelClient.create_streaming` does: feed the deltas to
    the hook, then return the assembled turn.
    """

    def __init__(self, turns: list[dict], answer: str, chunk: int = 7) -> None:
        super().__init__(turns)
        self._answer = answer
        self._chunk = chunk
        self.streamed_calls = 0

    async def create_streaming(
        self, conversation, tool_choice=None, timeout=None, on_text_delta=None
    ):
        self.streamed_calls += 1
        if on_text_delta is not None:
            for i in range(0, len(self._answer), self._chunk):
                await on_text_delta(self._answer[i : i + self._chunk])
        return say(self._answer)


def collect_streaming(model, messages, profile):
    loop = AgentLoop(client=_DirectClient(model), stream_answer_turn=True)

    async def go():
        events, result = [], None
        async for item in loop.stream(messages, profile):
            if isinstance(item, AgentRunResult):
                result = item
            else:
                events.append(item)
        return events, result

    return asyncio.run(go())


class _DirectClient(OpenAIModelClient):
    """Routes `create_streaming` at the scripted model instead of the SDK."""

    async def create_streaming(
        self, conversation, tool_choice=None, timeout=None, on_text_delta=None
    ):
        from app.agent.provider import normalize

        response = await self._client.create_streaming(
            conversation,
            tool_choice=tool_choice,
            timeout=timeout,
            on_text_delta=on_text_delta,
        )
        return normalize(response)


def test_answer_turn_streaming_emits_sentences_as_they_generate() -> None:
    answer = "The engine found no breaking point. Your buffer holds."
    model = StreamingScriptedModel(
        [call_tool("simulate", {"scenarios": []}), say("placeholder")], answer=answer
    )

    events, result = collect_streaming(model, user("How am I doing?"), maya_profile())

    assert model.streamed_calls == 1
    assert sentences(events).strip() == answer
    assert result.reply.startswith("The engine found no breaking point.")


def test_answer_turn_streaming_still_gates_ungrounded_figures() -> None:
    """Deltas do not get a pass — the gate runs on each settled sentence."""
    model = StreamingScriptedModel(
        [call_tool("simulate", {"scenarios": []}), say("placeholder")],
        answer="Your buffer holds. Your runway is 47.5 months.",
    )

    events, _ = collect_streaming(model, user("How am I doing?"), maya_profile())

    assert "47.5" not in sentences(events)
    assert any(isinstance(e, RetractEvent) for e in events)


def test_answer_turn_streaming_still_gates_blocked_advice() -> None:
    model = StreamingScriptedModel(
        [call_tool("simulate", {"scenarios": []}), say("placeholder")],
        answer="You should take out a payday loan.",
    )

    events, result = collect_streaming(model, user("What should I do?"), maya_profile())

    assert "payday" not in sentences(events).lower()
    assert result.guardrail.blocked is True


def test_a_provider_failure_on_the_first_call_raises_before_any_event() -> None:
    """The route relies on this to still return an honest 502."""
    loop = AgentLoop(client=OpenAIModelClient(ExplodingModel()))

    async def go():
        events = []
        with pytest.raises(AgentError):
            async for item in loop.stream(user("Hi"), maya_profile()):
                events.append(item)
        return events

    assert asyncio.run(go()) == []
