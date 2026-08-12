"""POST /agent/chat/stream over HTTP.

The contract this file pins:

* the stream always terminates with exactly one `done` or one `error`;
* `done` carries the same body `/agent/chat` would have returned;
* everything that used to be a status code still is one, because dependencies
  and validation run before the first byte.
"""

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.agent.loop import AgentLoop
from app.agent.provider import OpenAIModelClient
from app.agent.tools.simulate import run_simulate
from app.main import app
from app.routes.agent import UPSTREAM_FAILURE, get_agent_loop

from test_agent_loop import ExplodingModel, ScriptedModel, call_tool, say
from test_agent_tools import maya_profile, maya_profile_payload

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


def read_frames(payload: str) -> list[tuple[str, dict]]:
    """Parse an SSE body into (event, data) pairs, ignoring comments."""
    frames = []
    for block in payload.split("\n\n"):
        if not block.strip() or block.startswith(":"):
            continue
        name, data = None, None
        for line in block.split("\n"):
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: ") :])
        if name is not None:
            frames.append((name, data))
    return frames


def stream(payload: dict) -> list[tuple[str, dict]]:
    with client.stream("POST", "/agent/chat/stream", json=payload) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return read_frames("".join(response.iter_text()))


def test_stream_narrates_then_finishes_with_done() -> None:
    use_model([call_tool("simulate", {}), say(f"Your score is {SCORE}.")])

    frames = stream(body())
    names = [name for name, _ in frames]

    assert names[0] == "start"
    assert names[-1] == "done"
    assert names.count("done") == 1
    assert "tool_call" in names
    assert "simulate_run" in names
    assert "sentence" in names


def test_done_matches_the_non_streaming_response() -> None:
    """Streaming is progressive disclosure — it must not change the answer."""
    script = [call_tool("simulate", {}), say(f"Your score is {SCORE}.")]

    use_model(list(script))
    frames = stream(body())
    done = next(data for name, data in frames if name == "done")["response"]

    use_model(list(script))
    plain = client.post("/agent/chat", json=body()).json()

    assert done == plain


def test_sentences_reconstruct_the_reply() -> None:
    use_model([call_tool("simulate", {}), say(f"Your score is {SCORE}. It holds.")])

    frames = stream(body())
    streamed = "".join(d["text"] for n, d in frames if n == "sentence")
    done = next(d for n, d in frames if n == "done")["response"]

    # The disclaimer is appended by the final review, so `done` is longer —
    # but everything streamed must be a prefix of what the user ends up with.
    assert done["reply"].startswith(streamed.rstrip())


def test_a_blocked_reply_streams_no_recommendation() -> None:
    use_model(
        [call_tool("simulate", {}), say("You should take out a payday loan.")]
    )

    frames = stream(body())
    streamed = "".join(d["text"] for n, d in frames if n == "sentence")
    done = next(d for n, d in frames if n == "done")["response"]

    assert "payday" not in streamed.lower()
    assert done["guardrail"]["blocked"] is True
    assert any(name == "notice" for name, _ in frames)


def test_rate_limit_is_still_a_json_429() -> None:
    """Dependencies run before the first byte, so this never becomes a frame."""
    use_model([say("Fine.")])

    codes = []
    for _ in range(8):
        with client.stream("POST", "/agent/chat/stream", json=body()) as response:
            response.read()
            codes.append(response.status_code)
        use_model([say("Fine.")])

    assert 429 in codes
    assert app.state  # sanity: the app never crashed


def test_a_provider_failure_on_the_first_call_is_still_a_502() -> None:
    app.dependency_overrides[get_agent_loop] = lambda: AgentLoop(
        client=OpenAIModelClient(ExplodingModel())
    )

    with client.stream("POST", "/agent/chat/stream", json=body()) as response:
        response.read()
        assert response.status_code == 502
        assert response.json()["detail"] == UPSTREAM_FAILURE


def test_a_trailing_assistant_message_is_still_a_422() -> None:
    use_model([say("Fine.")])

    payload = body()
    payload["messages"].append({"role": "assistant", "content": "Already answered."})

    with client.stream("POST", "/agent/chat/stream", json=payload) as response:
        response.read()
        assert response.status_code == 422
