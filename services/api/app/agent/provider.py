"""The model provider seam.

Everything that knows OpenAI's wire vocabulary lives here. `loop.py` deals only
in `ModelTurn` and `ToolCall`, so porting providers again would mean rewriting
this file and nothing else.

The OpenAI Responses API differs from the Anthropic Messages API in six ways
that each fail *silently* if missed, which is why they're called out here:

1. The system prompt goes in `instructions=`, not a message.
2. Tool schemas are flat — `{"type","name","description","parameters"}` — with no
   nested `"function"` wrapper (that shape belongs to Chat Completions).
3. Tool arguments arrive as a **JSON string**, not a parsed object.
4. Results are echoed against `call_id` (`call_…`), never the item `id` (`fc_…`).
5. Results go back as bare `function_call_output` items with no `role`.
6. There is no `stop_reason` — a tool call is detected structurally, by finding
   `function_call` items in the output.
"""

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.agent.prompts import SYSTEM_PROMPT

#: Called with each text delta as it arrives. A side channel only — a streaming
#: call still returns a complete `ModelTurn`, so nothing downstream changes.
TextDeltaHook = Callable[[str], Awaitable[None]]

DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_MAX_OUTPUT_TOKENS = 16_000
# GPT-5.6 is a reasoning family. This agent routes to a tool and paraphrases
# JSON — it does no maths — so reasoning buys little here. Note "minimal" is
# rejected by 5.6 models; "none" is the correct off switch.
DEFAULT_EFFORT = "none"


class ProviderError(RuntimeError):
    """The model call failed. Carries a safe message plus the real one."""

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.detail = detail or message


class ConfigError(ProviderError):
    """Server is misconfigured (missing key, missing package)."""


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict
    #: Set when `arguments` wasn't valid JSON. Non-strict tools make this a live
    #: possibility, so it's data rather than an exception.
    parse_error: str | None = None


@dataclass(frozen=True)
class ModelTurn:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    #: The provider's own output items, echoed back verbatim on the next call.
    #: Includes reasoning items — dropping those breaks reasoning continuity
    #: across tool turns.
    raw_items: list[Any] = field(default_factory=list)
    refusal: str | None = None
    #: Why the response stopped early, e.g. "max_output_tokens".
    incomplete: str | None = None
    total_tokens: int = 0

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class ModelClient(Protocol):
    """What the loop needs from a provider."""

    async def create(
        self,
        conversation: list[Any],
        tool_choice: str | None = None,
        timeout: float | None = None,
    ) -> ModelTurn: ...


class StreamingModelClient(ModelClient, Protocol):
    """A provider that can also report text as it is generated.

    Separate from `ModelClient` so the scripted models in the test suite don't
    have to grow a method they never use; the loop feature-detects.
    """

    async def create_streaming(
        self,
        conversation: list[Any],
        tool_choice: str | None = None,
        timeout: float | None = None,
        on_text_delta: TextDeltaHook | None = None,
    ) -> ModelTurn: ...


def _get(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field from an SDK object or a plain dict (tests use dicts)."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_param(item: Any) -> Any:
    """Convert an output item into something safe to send back unchanged."""
    if isinstance(item, dict):
        return item
    dump = getattr(item, "model_dump", None)
    if callable(dump):
        return dump(exclude_none=True)
    return dict(vars(item))


def normalize(response: Any) -> ModelTurn:
    """Turn a Responses API result into the loop's provider-neutral shape."""
    import json

    output = list(_get(response, "output", []) or [])

    texts: list[str] = []
    refusals: list[str] = []
    tool_calls: list[ToolCall] = []

    for item in output:
        item_type = _get(item, "type")

        if item_type == "message":
            for part in _get(item, "content", []) or []:
                part_type = _get(part, "type")
                if part_type == "output_text":
                    texts.append(_get(part, "text", "") or "")
                elif part_type == "refusal":
                    refusals.append(_get(part, "refusal", "") or "")

        elif item_type == "function_call":
            raw_arguments = _get(item, "arguments", "") or "{}"
            parsed: dict = {}
            parse_error: str | None = None
            try:
                loaded = json.loads(raw_arguments)
                if isinstance(loaded, dict):
                    parsed = loaded
                else:
                    parse_error = "tool arguments must be a JSON object"
            except (TypeError, ValueError) as error:
                parse_error = f"tool arguments were not valid JSON: {error}"

            tool_calls.append(
                ToolCall(
                    # `call_id`, not `id` — echoing the wrong one silently
                    # fails to link the result to the call.
                    call_id=_get(item, "call_id") or "",
                    name=_get(item, "name", "") or "",
                    arguments=parsed,
                    parse_error=parse_error,
                )
            )

    incomplete = None
    if _get(response, "status") == "incomplete":
        details = _get(response, "incomplete_details") or {}
        incomplete = _get(details, "reason", "unknown") or "unknown"

    usage = _get(response, "usage") or {}

    return ModelTurn(
        text="\n\n".join(t for t in texts if t).strip(),
        tool_calls=tool_calls,
        raw_items=[_as_param(item) for item in output],
        refusal="\n".join(r for r in refusals if r) or None,
        incomplete=incomplete,
        total_tokens=int(_get(usage, "total_tokens", 0) or 0),
    )


def tool_result_item(call_id: str, payload: str) -> dict:
    """The Responses API shape for handing a tool result back.

    No `role` field, and `output` must be a string.
    """
    return {"type": "function_call_output", "call_id": call_id, "output": payload}


class OpenAIModelClient:
    """Thin wrapper over `client.responses.create`."""

    def __init__(
        self,
        client: Any,
        model: str | None = None,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        effort: str | None = None,
    ) -> None:
        self._client = client
        self.model = model or os.environ.get("OPENAI_MODEL") or DEFAULT_MODEL
        self.max_output_tokens = max_output_tokens
        self.effort = effort or os.environ.get("OPENAI_REASONING_EFFORT") or DEFAULT_EFFORT

    def _request(
        self,
        conversation: list[Any],
        tool_choice: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """The request body, built in one place.

        Shared by both call paths so `store=False`, `parallel_tool_calls`, the
        reasoning effort and the tool list cannot drift between them — only the
        non-streaming shape is covered by the schema tests.
        """
        from app.agent.tools import registry

        request: dict[str, Any] = {
            "model": self.model,
            "instructions": SYSTEM_PROMPT,
            "input": conversation,
            "tools": registry.tool_definitions(),
            "reasoning": {"effort": self.effort},
            "max_output_tokens": self.max_output_tokens,
            "parallel_tool_calls": False,
            # Financial conversations: don't leave them on the provider.
            "store": False,
        }
        if tool_choice is not None:
            request["tool_choice"] = tool_choice
        if timeout is not None:
            request["timeout"] = timeout
        return request

    async def create(
        self,
        conversation: list[Any],
        tool_choice: str | None = None,
        timeout: float | None = None,
    ) -> ModelTurn:
        try:
            response = await self._client.responses.create(
                **self._request(conversation, tool_choice, timeout)
            )
        except Exception as error:  # noqa: BLE001 — re-raised as a safe error
            raise ProviderError(
                "The model service is unavailable. Please try again.",
                detail=f"{type(error).__name__}: {error}",
            ) from error

        return normalize(response)

    async def create_streaming(
        self,
        conversation: list[Any],
        tool_choice: str | None = None,
        timeout: float | None = None,
        on_text_delta: TextDeltaHook | None = None,
    ) -> ModelTurn:
        """Same call, reporting text deltas as they arrive.

        Uses the SDK's `.stream()` helper and `get_final_response()`, which
        returns a fully assembled `Response` — so `normalize()` needs no changes,
        reasoning items survive intact (dropping them breaks reasoning continuity
        across tool turns), and `function_call.arguments` arrives already
        concatenated into the JSON *string* it expects.

        The lower-level `create(stream=True)` would force hand-rebuilding
        `raw_items`, which is exactly where the `call_id`-vs-`id` and
        reasoning-continuity bugs get reintroduced silently.
        """
        request = self._request(conversation, tool_choice, timeout)

        try:
            async with self._client.responses.stream(**request) as stream:
                async for event in stream:
                    if (
                        on_text_delta is not None
                        and _get(event, "type") == "response.output_text.delta"
                    ):
                        delta = _get(event, "delta", "") or ""
                        if delta:
                            await on_text_delta(delta)
                response = await stream.get_final_response()
        except Exception as error:  # noqa: BLE001 — re-raised as a safe error
            # Both entry and iteration are wrapped: streaming surfaces failures
            # mid-iteration, not only at call time.
            raise ProviderError(
                "The model service is unavailable. Please try again.",
                detail=f"{type(error).__name__}: {error}",
            ) from error

        return normalize(response)


def build_client(timeout_seconds: float = 45.0) -> Any:
    """Construct the shared AsyncOpenAI client. Raises if unusable."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise ConfigError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    try:
        from openai import AsyncOpenAI
    except ModuleNotFoundError as error:  # pragma: no cover — install-time only
        raise ConfigError(
            "The `openai` package is not installed. Run "
            "`pip install -r requirements.txt`."
        ) from error

    return AsyncOpenAI(timeout=timeout_seconds, max_retries=2)
