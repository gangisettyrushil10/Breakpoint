"""The loop, driven by a scripted model — no network, no API key.

The fake speaks the OpenAI Responses API's item shapes, including handing tool
arguments back as a **JSON string**. That detail matters: the previous fake
returned a parsed dict, which is why a missing `json.loads` was invisible.
"""

import asyncio
import json

import pytest

from app.agent.loop import (
    ITERATION_CAP_FALLBACK,
    REFUSAL_FALLBACK,
    TRUNCATION_NOTICE,
    AgentError,
    AgentLoop,
)
from app.agent.provider import OpenAIModelClient
from app.agent.schemas import ChatMessage
from app.agent.tools.simulate import run_simulate
from tests.test_agent_tools import maya_profile

# --------------------------------------------------------------------------
# The scripted model
# --------------------------------------------------------------------------


class ScriptedModel:
    """Stands in for `AsyncOpenAI`. Replays canned Responses payloads in order."""

    def __init__(self, turns: list[dict]) -> None:
        self._turns = list(turns)
        self.calls: list[dict] = []

    @property
    def responses(self) -> "ScriptedModel":
        return self

    async def create(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if not self._turns:
            raise AssertionError("model called more times than the script allows")
        return self._turns.pop(0)


class ExplodingModel:
    @property
    def responses(self) -> "ExplodingModel":
        return self

    async def create(self, **kwargs):
        raise RuntimeError("connection reset")


def message_item(text: str) -> dict:
    return {
        "type": "message",
        "role": "assistant",
        "status": "completed",
        "content": [{"type": "output_text", "text": text}],
    }


def function_call_item(
    name: str, arguments: dict, call_id: str = "call_1", item_id: str = "fc_1"
) -> dict:
    return {
        "type": "function_call",
        "id": item_id,
        "call_id": call_id,
        "name": name,
        # A JSON string, exactly as the API sends it.
        "arguments": json.dumps(arguments),
    }


def turn(*items: dict, status: str = "completed", reason: str | None = None) -> dict:
    payload: dict = {"status": status, "output": list(items)}
    if reason:
        payload["incomplete_details"] = {"reason": reason}
    return payload


def say(text: str) -> dict:
    return turn(message_item(text))


def call_tool(name: str, arguments: dict, call_id: str = "call_1", item_id: str = "fc_1") -> dict:
    return turn(function_call_item(name, arguments, call_id, item_id))


def preamble_then_call(text: str, name: str, arguments: dict) -> dict:
    """Text alongside a tool call — a preamble, never the final answer."""
    return turn(message_item(text), function_call_item(name, arguments))


def with_reasoning(payload: dict, item_id: str = "rs_1") -> dict:
    reasoning = {"type": "reasoning", "id": item_id, "summary": []}
    return {**payload, "output": [reasoning, *payload["output"]]}


def refuse(text: str = "I can't help with that.") -> dict:
    return turn(
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "refusal", "refusal": text}],
        }
    )


def truncated(text: str) -> dict:
    return turn(message_item(text), status="incomplete", reason="max_output_tokens")


def bad_json_call(name: str = "simulate", call_id: str = "call_1") -> dict:
    return turn(
        {
            "type": "function_call",
            "id": "fc_1",
            "call_id": call_id,
            "name": name,
            "arguments": '{"months": 6, "scenarios": [',  # truncated mid-object
        }
    )


def user(text: str) -> list[ChatMessage]:
    return [ChatMessage(role="user", content=text)]


def drive(model: ScriptedModel, messages, profile, **kwargs):
    """Run one async turn from a sync test."""
    loop = AgentLoop(client=OpenAIModelClient(model), **kwargs)
    return asyncio.run(loop.run(messages, profile))


SCORE = run_simulate(maya_profile(), months=6).resilience.score


# --------------------------------------------------------------------------
# The core invariant
# --------------------------------------------------------------------------


def test_an_invented_score_never_reaches_the_user() -> None:
    invented = SCORE + 23
    model = ScriptedModel(
        [
            call_tool("simulate", {"months": 6, "scenarios": []}),
            say(f"Your resilience score of {invented} puts you in rough shape."),
            say(f"Your resilience score of {SCORE} leaves little slack."),
        ]
    )

    result = drive(model, user("How resilient am I?"), maya_profile())

    assert str(invented) not in result.reply
    assert str(SCORE) in result.reply
    assert result.guardrail.regenerated is True


def test_a_reply_that_stays_ungrounded_is_withheld() -> None:
    invented = SCORE + 23
    model = ScriptedModel(
        [
            call_tool("simulate", {"months": 6, "scenarios": []}),
            say(f"Your resilience score of {invented} is rough."),
            say(f"I'll stand by it — your resilience score is {invented}."),
        ]
    )

    result = drive(model, user("How resilient am I?"), maya_profile())

    assert str(invented) not in result.reply
    assert result.guardrail.blocked is True
    assert result.simulate_result is not None


# --------------------------------------------------------------------------
# OpenAI wire shape
# --------------------------------------------------------------------------


def test_tool_result_uses_the_responses_item_shape() -> None:
    model = ScriptedModel([call_tool("simulate", {"months": 6}), say("Here you go.")])

    drive(model, user("Run it"), maya_profile())

    follow_up = model.calls[1]["input"]
    result_item = follow_up[-1]
    assert result_item["type"] == "function_call_output"
    # Linked by call_id, and it carries no role — this is an item, not a message.
    assert result_item["call_id"] == "call_1"
    assert "role" not in result_item
    assert isinstance(result_item["output"], str)
    payload = json.loads(result_item["output"])
    assert payload["result"]["resilience"]["score"] == SCORE


def test_the_item_id_is_never_echoed_as_the_call_id() -> None:
    """`fc_…` is the item id; `call_…` is the correlation id. Mixing them up
    silently fails to link the result to the call."""
    model = ScriptedModel(
        [call_tool("simulate", {}, call_id="call_abc", item_id="fc_xyz"), say("Done.")]
    )

    drive(model, user("Run it"), maya_profile())

    echoed = json.dumps(model.calls[1]["input"])
    assert '"call_id": "call_abc"' in echoed.replace(
        '"call_id":"call_abc"', '"call_id": "call_abc"'
    )
    assert '"call_id": "fc_xyz"' not in echoed


def test_arguments_arrive_as_a_json_string_and_are_parsed() -> None:
    model = ScriptedModel([call_tool("simulate", {"months": 3}), say("Done.")])

    result = drive(model, user("Three months"), maya_profile())

    assert result.tool_calls[0].arguments["months"] == 3
    assert len(result.simulate_runs[0].simulation.months) == 3


def test_system_prompt_rides_in_instructions_not_in_input() -> None:
    model = ScriptedModel([say("Hi.")])

    drive(model, user("Hello"), maya_profile())

    request = model.calls[0]
    assert "BreakPoint" in request["instructions"]
    assert all(item.get("role") != "system" for item in request["input"])


def test_tool_definitions_use_the_flat_responses_shape() -> None:
    model = ScriptedModel([say("Hi.")])

    drive(model, user("Hello"), maya_profile())

    tools = model.calls[0]["tools"]
    assert {tool["name"] for tool in tools} == {
        "simulate",
        "patch_profile",
        "estimate_commute_cost",
        "what_if",
        "explain_resilience_score",
        "plan_resilience_target",
    }
    for tool in tools:
        assert tool["type"] == "function"
        assert "parameters" in tool
        # The nested wrapper belongs to Chat Completions; input_schema to Anthropic.
        assert "function" not in tool
        assert "input_schema" not in tool


def test_reasoning_items_are_echoed_back_verbatim() -> None:
    model = ScriptedModel(
        [with_reasoning(call_tool("simulate", {})), say("Done.")]
    )

    drive(model, user("Run it"), maya_profile())

    echoed = model.calls[1]["input"]
    assert {"type": "reasoning", "id": "rs_1", "summary": []} in echoed


def test_reasoning_effort_is_none_never_minimal() -> None:
    model = ScriptedModel([say("Hi.")])

    drive(model, user("Hello"), maya_profile())

    assert model.calls[0]["reasoning"] == {"effort": "none"}
    assert model.calls[0]["store"] is False


# --------------------------------------------------------------------------
# Loop correctness
# --------------------------------------------------------------------------


def test_preamble_text_never_becomes_the_final_reply() -> None:
    """Text alongside a tool call is a preamble. Serving it as the answer was
    the bug that made the iteration-cap fallback unreachable."""
    model = ScriptedModel(
        [
            preamble_then_call("Let me check that for you.", "simulate", {}),
            say(f"Your score is {SCORE}."),
        ]
    )

    result = drive(model, user("How am I doing?"), maya_profile())

    assert "Let me check that for you." not in result.reply
    assert str(SCORE) in result.reply


def test_speculation_before_a_tool_call_is_not_served_as_the_answer() -> None:
    invented = SCORE + 41
    model = ScriptedModel(
        [
            preamble_then_call(
                f"I think your score is around {invented}.", "patch_profile",
                {"savings": {"liquidCents": 100_000}},
            ),
            turn(),  # a legal empty response
        ]
    )

    result = drive(model, user("I have $1k saved"), maya_profile())

    assert str(invented) not in result.reply


def test_the_cap_triggers_a_finalizer_rather_than_a_preamble() -> None:
    model = ScriptedModel(
        [
            preamble_then_call("Working on it.", "simulate", {}),
            preamble_then_call("Still working.", "simulate", {}),
            say(f"Your score is {SCORE}."),  # the finalizer call
        ]
    )

    result = drive(model, user("Loop"), maya_profile(), max_iterations=2)

    assert result.stop_reason == "max_iterations"
    assert model.calls[-1]["tool_choice"] == "none"
    assert str(SCORE) in result.reply
    assert "Working on it." not in result.reply


def test_the_cap_falls_back_when_the_finalizer_says_nothing() -> None:
    model = ScriptedModel(
        [call_tool("simulate", {}), call_tool("simulate", {}), turn()]
    )

    result = drive(model, user("Loop"), maya_profile(), max_iterations=2)

    assert result.stop_reason == "max_iterations"
    assert ITERATION_CAP_FALLBACK in result.reply


def test_truncated_replies_say_so() -> None:
    model = ScriptedModel(
        [
            call_tool("simulate", {}),
            truncated(f"Your score is {SCORE}, which means you can cover"),
        ]
    )

    result = drive(model, user("Explain"), maya_profile())

    assert result.stop_reason == "truncated"
    assert TRUNCATION_NOTICE.strip() in result.reply


def test_editing_the_profile_invalidates_earlier_simulations() -> None:
    """Numbers from before the edit describe a budget that no longer exists."""
    model = ScriptedModel(
        [
            call_tool("simulate", {"months": 6, "scenarios": []}),
            call_tool(
                "patch_profile",
                {"savings": {"liquidCents": 100_000}},
                call_id="call_2",
            ),
            say(f"Your score is {SCORE}."),  # the pre-edit score
            say("Your savings changed; ask me to re-run the numbers."),
        ]
    )

    result = drive(model, user("I only have $1k saved"), maya_profile())

    assert result.profile.savings.liquidCents == 100_000
    assert result.simulate_runs == []
    # The stale score is no longer quotable, so it must not survive.
    assert str(SCORE) not in result.reply


def test_the_dashboard_gets_the_baseline_run_not_the_stress_run() -> None:
    model = ScriptedModel(
        [
            call_tool("simulate", {"months": 6, "scenarios": []}),
            call_tool(
                "simulate",
                {
                    "months": 6,
                    "scenarios": [
                        {"type": "car_repair", "monthIndex": 2, "costCents": 240_000}
                    ],
                },
                call_id="call_2",
            ),
            say("A repair would bite, but you hold."),
        ]
    )

    result = drive(model, user("Compare a repair to today"), maya_profile())

    assert len(result.simulate_runs) == 2
    baseline = run_simulate(maya_profile(), months=6)
    assert result.simulate_result is not None
    assert result.simulate_result.resilience == baseline.resilience


# --------------------------------------------------------------------------
# Failures
# --------------------------------------------------------------------------


def test_malformed_tool_arguments_are_reported_to_the_model() -> None:
    model = ScriptedModel([bad_json_call(), say("Let me try that again.")])

    result = drive(model, user("Run it"), maya_profile())

    assert result.tool_calls[0].ok is False
    payload = json.loads(model.calls[1]["input"][-1]["output"])
    assert payload["error"] == "invalid_arguments_json"


def test_tool_errors_come_back_as_data_not_exceptions() -> None:
    model = ScriptedModel(
        [
            call_tool(
                "simulate",
                {"months": 3, "scenarios": [{"type": "car_repair", "monthIndex": 8}]},
            ),
            say("That shock lands past the horizon — want me to extend it?"),
        ]
    )

    result = drive(model, user("Repair in month 9"), maya_profile())

    assert result.tool_calls[0].ok is False
    assert result.simulate_runs == []
    assert json.loads(model.calls[1]["input"][-1]["output"])["ok"] is False


def test_repeated_tool_failures_stop_the_loop_early() -> None:
    model = ScriptedModel([bad_json_call(), bad_json_call(), turn()])

    result = drive(model, user("Run it"), maya_profile(), max_iterations=5)

    assert result.stop_reason == "tool_failures"
    # Two failed attempts, then the finalizer — not five iterations burned.
    assert len(model.calls) == 3


def test_unknown_tool_does_not_crash_the_turn() -> None:
    model = ScriptedModel(
        [call_tool("fetch_gas_prices", {}), say("I can't look that up yet.")]
    )

    result = drive(model, user("Gas prices?"), maya_profile())

    assert result.tool_calls[0].ok is False
    assert "I can't look that up yet." in result.reply


def test_refusal_short_circuits_the_turn() -> None:
    model = ScriptedModel([refuse()])

    result = drive(model, user("..."), maya_profile())

    assert result.stop_reason == "refusal"
    assert REFUSAL_FALLBACK in result.reply


def test_client_failures_surface_as_agent_error() -> None:
    loop = AgentLoop(client=OpenAIModelClient(ExplodingModel()))

    with pytest.raises(AgentError) as caught:
        asyncio.run(loop.run(user("Hi"), maya_profile()))

    # The user-facing message is generic; the real cause is kept for the log.
    assert "connection reset" not in str(caught.value)
    assert "connection reset" in caught.value.detail


def test_blocked_advice_never_reaches_the_reply() -> None:
    model = ScriptedModel(
        [say("You should take out a payday loan to cover the shortfall.")]
    )

    result = drive(model, user("What do I do?"), maya_profile())

    assert result.guardrail.blocked is True
    assert "payday" not in result.reply.lower()


# --------------------------------------------------------------------------
# Horizon plumbing
# --------------------------------------------------------------------------


def test_requested_horizon_becomes_the_tools_default() -> None:
    model = ScriptedModel([call_tool("simulate", {}), say("Done.")])
    loop = AgentLoop(client=OpenAIModelClient(model))

    result = asyncio.run(loop.run(user("Run it"), maya_profile(), months=12))

    assert result.tool_calls[0].arguments["months"] == 12
    assert len(result.simulate_runs[0].simulation.months) == 12


def test_model_can_override_the_default_horizon() -> None:
    model = ScriptedModel([call_tool("simulate", {"months": 3}), say("Done.")])
    loop = AgentLoop(client=OpenAIModelClient(model))

    result = asyncio.run(loop.run(user("Three months?"), maya_profile(), months=12))

    assert result.tool_calls[0].arguments["months"] == 3
