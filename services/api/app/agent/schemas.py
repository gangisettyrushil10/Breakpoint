"""Wire contract for POST /agent/chat.

The client owns the conversation: it sends the full message history and the
working profile on every turn, and gets both back. No server session, no
database — Phase 2 keeps the agent stateless.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.financial_profile import FinancialProfile
from app.routes.simulate import SimulateResponse

MAX_MESSAGES = 40
MAX_CONTENT_CHARS = 4_000
#: The whole transcript is resent on every loop iteration, so this is the real
#: cost ceiling for a turn — the per-message limits alone would allow ~160KB.
MAX_TRANSCRIPT_CHARS = 24_000


class ChatMessage(BaseModel):
    """One visible turn. Tool traffic is not represented here."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_CONTENT_CHARS)


class ToolCallRecord(BaseModel):
    """What the agent actually ran, so the UI can show its work."""

    name: str
    arguments: dict
    ok: bool


class GuardrailReport(BaseModel):
    """Why the reply was blocked, regenerated, or withheld — if it was."""

    blocked: bool = False
    regenerated: bool = False
    #: Figures the model stated that the tool output couldn't account for.
    unsupported: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    #: Deprecated. Numbers are no longer rewritten in place — a reply with an
    #: ungrounded figure is regenerated or withheld instead. Kept so the wire
    #: contract doesn't break; always False.
    amended: bool = False


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    profile: FinancialProfile
    months: int = Field(default=6, ge=1, le=12)

    @model_validator(mode="after")
    def transcript_must_fit_the_budget(self) -> "ChatRequest":
        total = sum(len(message.content) for message in self.messages)
        if total > MAX_TRANSCRIPT_CHARS:
            raise ValueError(
                f"Conversation is too long ({total} characters; the limit is "
                f"{MAX_TRANSCRIPT_CHARS}). Start a new chat."
            )
        return self


class ChatResponse(BaseModel):
    """Everything the client needs to render the turn and update the dashboard."""

    messages: list[ChatMessage]
    reply: str
    profile: FinancialProfile
    #: The run describing the user's actual situation — the unstressed one where
    #: the turn simulated several. This is what the dashboard should render.
    simulateResult: SimulateResponse | None = None
    #: Every simulation this turn, in call order (a turn may compare scenarios).
    simulateRuns: list[SimulateResponse] = Field(default_factory=list)
    toolCalls: list[ToolCallRecord] = Field(default_factory=list)
    guardrail: GuardrailReport = Field(default_factory=GuardrailReport)
    stopReason: str | None = None
    #: Tokens across every model call this turn. The whole transcript is resent
    #: on each loop iteration, so this — not the reply length — is what a turn
    #: actually costs.
    totalTokens: int = 0
    #: How many times the model was called. Two is the normal shape: one to pick
    #: a tool, one to explain what came back.
    modelCalls: int = 0
