"""POST /agent/chat over HTTP, with a scripted model swapped in via DI."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.agent.loop import AgentError, AgentLoop
from app.agent.provider import OpenAIModelClient
from app.agent.schemas import MAX_TRANSCRIPT_CHARS
from app.agent.tools.simulate import run_simulate
from app.main import app
from app.routes.agent import UPSTREAM_FAILURE, get_agent_loop
from tests.test_agent_loop import ScriptedModel, call_tool, say
from tests.test_agent_tools import maya_profile, maya_profile_payload

client = TestClient(app)

SCORE = run_simulate(maya_profile(), months=6).resilience.score


@pytest.fixture(autouse=True)
def clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()
    app.state.openai_client = None


def use_model(turns: list[dict]) -> ScriptedModel:
    model = ScriptedModel(turns)
    app.dependency_overrides[get_agent_loop] = lambda: AgentLoop(
        client=OpenAIModelClient(model)
    )
    return model


def body(text: str = "How resilient am I?", **overrides) -> dict:
    return {
        "messages": [{"role": "user", "content": text}],
        "profile": maya_profile_payload(),
        "months": 6,
        **overrides,
    }


def test_chat_returns_transcript_and_simulation() -> None:
    use_model([call_tool("simulate", {}), say(f"Your score is {SCORE}.")])

    response = client.post("/agent/chat", json=body())

    assert response.status_code == 200
    data = response.json()

    assert str(SCORE) in data["reply"]
    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
    assert data["messages"][-1]["content"] == data["reply"]
    assert data["toolCalls"] == [
        {"name": "simulate", "arguments": {"months": 6}, "ok": True}
    ]
    assert data["stopReason"] == "completed"


def test_visible_numbers_equal_the_tool_json() -> None:
    """The acceptance bar for the whole feature, checked over HTTP."""
    expected = run_simulate(maya_profile(), months=6)
    use_model([call_tool("simulate", {}), say(f"Your score is {SCORE}.")])

    data = client.post("/agent/chat", json=body()).json()

    assert data["simulateResult"] == expected.model_dump()
    assert data["simulateRuns"] == [expected.model_dump()]


def test_an_invented_figure_does_not_reach_the_client() -> None:
    invented = SCORE + 30
    use_model(
        [
            call_tool("simulate", {}),
            say(f"Your resilience score of {invented} is rough."),
            say(f"Your resilience score is {SCORE}."),
        ]
    )

    data = client.post("/agent/chat", json=body()).json()

    assert str(invented) not in data["reply"]
    assert data["guardrail"]["regenerated"] is True


def test_chat_echoes_a_patched_profile_back_to_the_client() -> None:
    use_model(
        [
            call_tool("patch_profile", {"savings": {"liquidCents": 100_000}}),
            say("Updated — ask me to re-run the numbers."),
        ]
    )

    data = client.post("/agent/chat", json=body("I only have $1k saved")).json()

    assert data["profile"]["savings"]["liquidCents"] == 100_000


def test_chat_blocks_dangerous_advice() -> None:
    use_model([say("You should take out a payday loan to cover it.")])

    data = client.post("/agent/chat", json=body("What should I do?")).json()

    assert data["guardrail"]["blocked"] is True
    assert "payday" not in data["reply"].lower()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_chat_requires_the_last_message_to_be_from_the_user() -> None:
    use_model([say("unused")])

    response = client.post(
        "/agent/chat",
        json=body() | {"messages": [{"role": "assistant", "content": "Hi"}]},
    )

    assert response.status_code == 422


def test_chat_rejects_an_empty_transcript() -> None:
    use_model([say("unused")])

    assert client.post("/agent/chat", json=body() | {"messages": []}).status_code == 422


def test_chat_rejects_an_oversized_transcript() -> None:
    """The whole transcript is resent on every loop iteration, so this is the
    real cost ceiling for one turn."""
    use_model([say("unused")])
    huge = [
        {"role": "user", "content": "x" * 3_000} for _ in range(MAX_TRANSCRIPT_CHARS // 3_000 + 2)
    ]

    response = client.post("/agent/chat", json=body() | {"messages": huge})

    assert response.status_code == 422


def test_chat_rejects_an_invalid_profile() -> None:
    use_model([say("unused")])
    bad = maya_profile_payload()
    bad["income"]["monthlyTakeHomeCents"] = -5

    assert client.post("/agent/chat", json=body() | {"profile": bad}).status_code == 422


def test_chat_rejects_an_out_of_range_horizon() -> None:
    use_model([say("unused")])

    assert client.post("/agent/chat", json=body() | {"months": 24}).status_code == 422


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------


def test_missing_api_key_becomes_a_502_not_a_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The key check runs during dependency resolution, outside the route
    body's error handling — so it has to be translated there."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app.state.openai_client = None

    response = client.post("/agent/chat", json=body())

    assert response.status_code == 502
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_model_failure_becomes_a_502_without_leaking_provider_detail() -> None:
    class Failing:
        async def run(self, **kwargs):
            raise AgentError(
                "The model service is unavailable. Please try again.",
                detail="RateLimitError: org-abc123 exceeded quota, request req_xyz",
            )

    app.dependency_overrides[get_agent_loop] = lambda: Failing()

    response = client.post("/agent/chat", json=body())

    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail == UPSTREAM_FAILURE
    # The provider's own text can carry request ids and org detail.
    assert "org-abc123" not in detail
    assert "req_xyz" not in detail


def test_rate_limit_returns_429_after_a_burst() -> None:
    use_model([say("ok")] * 40)

    codes = [
        client.post("/agent/chat", json=body()).status_code for _ in range(10)
    ]

    assert 429 in codes
    assert codes[0] == 200
    limited = client.post("/agent/chat", json=body())
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers


def test_simulate_route_still_works_alongside_the_agent() -> None:
    response = client.post(
        "/simulate",
        json={"profile": maya_profile_payload(), "months": 6, "scenarios": []},
    )

    assert response.status_code == 200
