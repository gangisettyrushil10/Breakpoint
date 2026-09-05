"""Tool name -> handler, and the schemas the model sees.

Every handler has the same shape:

    handle(profile: FinancialProfile, arguments: dict) -> dict

The dict is JSON-serialisable and becomes the `tool_result` content. Handlers
return errors as data (`{"ok": False, ...}`) rather than raising, so a bad
argument gives the model a chance to correct itself instead of failing the
whole request.
"""

from collections.abc import Callable
from typing import Any, Protocol

from app.agent.tools import (
    commute_cost,
    explain_score,
    patch_profile,
    plan_resilience,
    simulate,
    what_if,
)
from app.domain.financial_profile import FinancialProfile


def openai_safe_schema(node: Any) -> Any:
    """Normalise a pydantic JSON Schema for the OpenAI Responses API.

    Two transformations, both lossless for our purposes:

    * ``oneOf`` -> ``anyOf``. Pydantic emits ``oneOf`` for the discriminated
      scenario union; ``anyOf`` is the form OpenAI documents support for. Each
      branch still carries ``{"type": {"const": ...}}``, so the model keeps the
      signal that told it which variant to pick, and the handler validates with
      pydantic either way.
    * ``title`` and ``discriminator`` are dropped. Neither constrains anything,
      and pydantic generates a title for every field — pure prompt cost on a
      schema that is resent on every call.

    Generating from pydantic and normalising here keeps one source of truth, so
    the schema can't drift from the models the handlers actually validate with.
    """
    if isinstance(node, dict):
        cleaned = {
            key: openai_safe_schema(value)
            for key, value in node.items()
            if key not in {"title", "discriminator"}
        }
        if "oneOf" in cleaned:
            cleaned["anyOf"] = cleaned.pop("oneOf")
        return cleaned
    if isinstance(node, list):
        return [openai_safe_schema(item) for item in node]
    return node


class ToolHandler(Protocol):
    def __call__(self, profile: FinancialProfile, arguments: dict) -> dict: ...


class Tool:
    """A tool the model can call, paired with the code that runs it."""

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Callable[[], dict],
        handler: ToolHandler,
        mutates_profile: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        self._input_schema = input_schema
        self.handler = handler
        self.mutates_profile = mutates_profile

    def definition(self) -> dict:
        """The OpenAI Responses tool definition.

        Flat by design: `name`/`description`/`parameters` sit beside `type`.
        The nested `{"function": {...}}` wrapper belongs to Chat Completions and
        is rejected here.

        `strict` stays off deliberately. Strict mode requires every property in
        `required`, which would destroy the scenario defaults (a car repair
        would have to carry an explicit `costCents` instead of its preset), and
        it can't express the scenario discriminated union at all. The handlers
        already validate with pydantic and hand back `{"ok": false, "detail": …}`,
        which lets the model correct itself.
        """
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": openai_safe_schema(self._input_schema()),
            "strict": False,
        }


REGISTRY: dict[str, Tool] = {
    simulate.TOOL_NAME: Tool(
        name=simulate.TOOL_NAME,
        description=simulate.TOOL_DESCRIPTION,
        input_schema=simulate.input_schema,
        handler=simulate.handle,
    ),
    patch_profile.TOOL_NAME: Tool(
        name=patch_profile.TOOL_NAME,
        description=patch_profile.TOOL_DESCRIPTION,
        input_schema=patch_profile.input_schema,
        handler=patch_profile.handle,
        mutates_profile=True,
    ),
    # Reaches the network, unlike its neighbours. It cannot change the profile:
    # a looked-up figure is a proposal the user confirms, and confirming means
    # the model calling patch_profile with it.
    commute_cost.TOOL_NAME: Tool(
        name=commute_cost.TOOL_NAME,
        description=commute_cost.TOOL_DESCRIPTION,
        input_schema=commute_cost.input_schema,
        handler=commute_cost.handle,
    ),
    # Runs the engine over a modified *copy*. Emphatically non-mutating: the
    # whole point is asking "what would this cost me?" without committing to it.
    what_if.TOOL_NAME: Tool(
        name=what_if.TOOL_NAME,
        description=what_if.TOOL_DESCRIPTION,
        input_schema=what_if.input_schema,
        handler=what_if.handle,
    ),
    explain_score.TOOL_NAME: Tool(
        name=explain_score.TOOL_NAME,
        description=explain_score.TOOL_DESCRIPTION,
        input_schema=explain_score.input_schema,
        handler=explain_score.handle,
    ),
    plan_resilience.TOOL_NAME: Tool(
        name=plan_resilience.TOOL_NAME,
        description=plan_resilience.TOOL_DESCRIPTION,
        input_schema=plan_resilience.input_schema,
        handler=plan_resilience.handle,
    ),
}


def tool_definitions() -> list[dict]:
    """Tool list for the model. Order is stable so the prompt cache holds."""
    return [REGISTRY[name].definition() for name in sorted(REGISTRY)]


def get(name: str) -> Tool | None:
    return REGISTRY.get(name)


def dispatch(name: str, profile: FinancialProfile, arguments: dict) -> dict:
    """Run a tool by name. An unknown name is data, not an exception."""
    tool = REGISTRY.get(name)
    if tool is None:
        return {
            "ok": False,
            "error": "unknown_tool",
            "detail": f"No tool named {name!r}. Available: {sorted(REGISTRY)}.",
        }
    return tool.handler(profile=profile, arguments=arguments)
