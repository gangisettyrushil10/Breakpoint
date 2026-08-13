"""What a streaming turn can tell the client while it is still running.

Deliberately free of imports from `loop.py` — the loop emits these, and its
`stream()` yields the final `AgentRunResult` as the last item rather than
wrapping it in an event, so nothing here needs to know about the loop's types.

The client contract in one line: **`done` replaces everything.** Every event
below is progressive disclosure, and the final `ChatResponse` is authoritative.
That is what makes streaming unable to change the answer — see
`tests/test_agent_stream.py`, which asserts a streamed turn and a non-streamed
turn produce identical results.
"""

from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True)
class StartEvent:
    """The commit point.

    Emitted after the *first* successful provider call, not at the top of the
    turn. The route pulls this one eagerly, so a provider failure on the opening
    call is still an honest HTTP 502 instead of an error frame on a 200 the
    client already committed to.
    """

    months: int
    type: Literal["start"] = "start"


@dataclass(frozen=True)
class ToolCallEvent:
    """A tool ran. Mirrors `ToolCallRecord` so the EnginePanel can render it."""

    name: str
    arguments: dict
    ok: bool
    type: Literal["tool_call"] = "tool_call"


@dataclass(frozen=True)
class SimulateRunEvent:
    """A simulation finished.

    `hasScenarios` is here because which run describes the user's *actual*
    situation is only decidable at the end — `_TurnState.dashboard_result()`
    prefers the most recent scenario-free run. The client can apply the same
    rule optimistically; `done.simulateResult` remains authoritative.
    """

    index: int
    hasScenarios: bool
    result: Any
    type: Literal["simulate_run"] = "simulate_run"


@dataclass(frozen=True)
class WhatIfEvent:
    """A hypothetical comparison finished.

    Deliberately not a `ProfileEvent`: nothing has changed, and a client that
    treated this as an edit would show the user a budget they never agreed to.
    Carries only what a panel needs to render a before → after.
    """

    scoreBefore: int
    scoreAfter: int
    changed: Any
    type: Literal["what_if"] = "what_if"


@dataclass(frozen=True)
class ProfileEvent:
    """The agent edited the profile via a `mutates_profile` tool."""

    profile: Any
    type: Literal["profile"] = "profile"


@dataclass(frozen=True)
class SentenceEvent:
    """One gate-cleared sentence, with the whitespace that followed it."""

    text: str
    type: Literal["sentence"] = "sentence"


@dataclass(frozen=True)
class RetractEvent:
    """Clear the bubble — never append a correction.

    A visible wrong figure with a correction underneath is the invariant
    violation with extra steps, and the clean prefix isn't innocent either: it
    was written to justify the bad number. `guardrails.py` makes exactly this
    argument about substituting values in place.
    """

    reason: str
    type: Literal["retract"] = "retract"


@dataclass(frozen=True)
class NoticeEvent:
    """Something the user should know about how the reply was produced."""

    kind: Literal["regenerating", "withheld", "blocked"]
    detail: str = ""
    type: Literal["notice"] = "notice"


@dataclass(frozen=True)
class ErrorEvent:
    """A post-commit failure. Terminal — nothing follows it."""

    detail: str
    type: Literal["error"] = "error"


AgentEvent = (
    StartEvent
    | ToolCallEvent
    | SimulateRunEvent
    | WhatIfEvent
    | ProfileEvent
    | SentenceEvent
    | RetractEvent
    | NoticeEvent
    | ErrorEvent
)
