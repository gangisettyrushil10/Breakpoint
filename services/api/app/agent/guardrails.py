"""Output guardrails: block advice we won't give, catch numbers we didn't compute.

Two independent checks over the model's final visible reply.

**Numbers** are checked against `grounding.Ledger` — the closed set of values the
tool actually returned. An earlier version tried to *correct* wrong figures in
place; that was removed deliberately. Substituting a value into a sentence
written to justify a different one produces a fluent falsehood
("your runway of 14 months is plenty" -> "...2.3 months is plenty"), and it
breaks the product invariant on its own terms: the user ends up reading a
sentence the model never wrote about numbers it never had. The reply is now
regenerated or withheld instead.

**Advice** is still a blocklist, because the set of things we will never
recommend is small and closed. The rules match on recommendation phrasing and
then run a negation filter, so explaining *why* a payday loan is expensive —
which the system prompt explicitly asks for — is not mistaken for recommending
one.
"""

import re
from dataclasses import dataclass, field

from app.agent.grounding import Ledger, unsupported_numbers

DISCLAIMER = (
    "This is an educational projection, not financial advice — it only knows the "
    "numbers in your profile."
)

BLOCKED_REPLACEMENT = (
    "I can't point you toward that one. High-cost credit and missed essentials "
    "usually pull a breaking point closer rather than pushing it out, and I can't "
    "price those products from your profile, so I'd be guessing at the part that "
    "matters most.\n\n"
    "What I can do is show you what actually moves your breaking point. Ask me to "
    "re-run the simulation and I'll walk through the prevention levers it returns."
)

UNGROUNDED_PREAMBLE = (
    "I couldn't answer that without stating figures the simulation didn't produce, "
    "so I'd rather give you only what the engine actually returned:"
)
UNGROUNDED_BARE = (
    "I couldn't answer that without stating figures the simulation didn't produce. "
    "Ask me to run the numbers and I'll walk you through what comes back."
)

_FLAGS = re.IGNORECASE | re.VERBOSE

# Phrases that read as "here is a thing you should do".
# `consider` and `try` were removed: bare `consider` matched inside "considering",
# so "if you are considering a payday loan, here is why it's expensive" was
# blocked, and `try` is unrecoverably ambiguous ("try to save more").
_ADVICE_CUE = r"""(?:
      \byou\s+(?:should|could|can|might\s+want\s+to|ought\s+to|'?ll\s+want\s+to)\b
    | \bi(?:'d|\s+would)?\s+(?:recommend|suggest|advise)\b
    | \bmy\s+advice\s+is\b
    | \b(?:one|another|your\s+best)\s+(?:option|bet|move)\s+(?:is|would\s+be)\b
    | \bit\s+(?:makes\s+sense|would\s+make\s+sense)\s+to\b
    | \blook\s+into\b
    | \btake\s+out\b
    | \btaking\s+out\b
    | \bapply\s+for\b
    | \bgo\s+with\b
    | \breach\s+for\b
)"""

_HIGH_COST_CREDIT = r"""(?:
      payday\s+(?:loan|lender|advance)
    | (?:car\s+)?title\s+loan
    | pawn(?:shop|ing|\s+your)
    | cash[-\s]advance\s+app
    | earned\s+wage\s+access
    | debt\s+settlement
    | refund\s+anticipation\s+loan
    | rent[-\s]to[-\s]own
    | 401\(?k\)?\s+(?:loan|withdrawal)
    | (?:tap|raid|cash\s+out|borrow\s+against|dip\s+into|withdraw\s+from)
      (?:\s+\w+){0,2}\s+(?:401\(?k\)?|ira|retirement)
    | (?:early|earlier)\s+withdrawal\s+from\s+(?:your\s+)?(?:401|ira|retirement)
    | withdrawing\s+from\s+(?:your\s+)?(?:401|ira|retirement)
)"""

_SKIP_ESSENTIAL = r"""(?:
    (?:skip|skipping|miss|missing|delay|delaying|defer|deferring|stop\s+paying|
       not\s+pay|hold\s+off\s+on|pause|put\s+off|let\s+\w+\s+go\s+to\s+collections)
    [^.!?]{0,40}?
    (?:rent|mortgage|utilit|insurance|minimum\s+payment|electric\s+bill|
       water\s+bill|car\s+payment)
)"""

_CREDENTIALS = r"""(?:
      (?:social\s+security|ssn)\s+number
    | \bssn\b
    | (?:bank\s+)?account\s+number
    | routing\s+number
    | (?:credit\s+)?card\s+number
    | (?:your\s+)?(?:password|login\s+credentials|online\s+banking\s+login)
)"""

# "A payday loan is your fastest way out" — the product leads, so a
# cue-then-product rule never sees it.
_TRAILING_RECOMMENDATION = rf"""(?:
    {_HIGH_COST_CREDIT}
    [^.!?]{{0,60}}?
    (?:
        (?:is|would\s+be|remains)\s+(?:your|the)\s+
        (?:best|fastest|quickest|only|simplest|easiest)\s+
        (?:option|bet|way|move|route|choice)
      | could\s+(?:cover|bridge|get\s+you\s+through|tide\s+you\s+over)
      | would\s+(?:cover|bridge|get\s+you\s+through)
    )
)"""

_IMPERATIVE_PRODUCT = rf"""(?:
    (?:^|[.!?]\s+|\n)\s*
    (?:take\s+out|apply\s+for|get|use|consider)\s+
    [^.!?]{{0,40}}?
    {_HIGH_COST_CREDIT}
)"""

BLOCK_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "recommended a high-cost credit product",
        re.compile(rf"{_ADVICE_CUE}[^.!?]{{0,60}}?{_HIGH_COST_CREDIT}", _FLAGS),
    ),
    (
        "recommended a high-cost credit product",
        re.compile(_TRAILING_RECOMMENDATION, _FLAGS),
    ),
    (
        "recommended a high-cost credit product",
        re.compile(_IMPERATIVE_PRODUCT, _FLAGS),
    ),
    (
        "recommended skipping an essential payment",
        re.compile(rf"{_ADVICE_CUE}[^.!?]{{0,40}}?{_SKIP_ESSENTIAL}", _FLAGS),
    ),
    (
        "asked for credentials or account identifiers",
        re.compile(
            rf"(?:what(?:'s|\s+is)|share|send|provide|enter|give\s+me|paste|type)"
            rf"[^.!?]{{0,40}}?{_CREDENTIALS}",
            _FLAGS,
        ),
    ),
]

# If any of these sit in the same sentence, the model is warning against the
# thing, not recommending it. The system prompt tells it to do exactly that.
_DISCOURAGEMENT = re.compile(
    r"\b(?:don'?t|do\s+not|never|avoid|steer\s+clear|rather\s+than|instead\s+of|"
    r"stay\s+away|resist|can'?t\s+recommend|won'?t\s+recommend|wouldn'?t\s+recommend|"
    r"beware|not\s+worth|bad\s+idea|last\s+resort|shouldn'?t|should\s+not)\b",
    re.IGNORECASE,
)

_SENTENCES = re.compile(r"(?<=[.!?])\s+|\n+")


@dataclass
class GuardrailVerdict:
    text: str
    blocked: bool = False
    regenerate_requested: bool = False
    unsupported: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


def find_blocked_reasons(text: str) -> list[str]:
    """Reasons this text must not be shown, deduplicated in rule order.

    Matching is per sentence so the discouragement filter can be scoped to the
    clause that actually matched.
    """
    found: list[str] = []

    for sentence in _SENTENCES.split(text or ""):
        if not sentence.strip() or _DISCOURAGEMENT.search(sentence):
            continue
        for reason, pattern in BLOCK_RULES:
            if pattern.search(sentence) and reason not in found:
                found.append(reason)

    return found


def with_disclaimer(text: str) -> str:
    """Append the disclaimer unless the model already said something like it."""
    if "not financial advice" in text.lower() or DISCLAIMER in text:
        return text
    return f"{text.rstrip()}\n\n{DISCLAIMER}"


def ungrounded_fallback(ledger: Ledger) -> str:
    """A reply built from the ledger, so every figure in it is grounded."""
    lines = ledger.summary_lines()
    if not lines:
        return UNGROUNDED_BARE
    return "\n".join([UNGROUNDED_PREAMBLE, "", *lines])


@dataclass(frozen=True)
class SentenceVerdict:
    """One settled sentence, and whether it may leave the server."""

    #: The fragment as `_SENTENCES.split` would produce it — delimiter removed.
    text: str
    #: The delimiter that followed it. `split` consumes it, so the gate carries
    #: it separately; `text + separator` rebuilds the original stream.
    separator: str
    ok: bool
    reasons: list[str] = field(default_factory=list)
    unsupported: list[str] = field(default_factory=list)


def review_sentence(sentence: str, ledger: Ledger) -> SentenceVerdict:
    """Both checks over exactly one sentence.

    Pure, and deliberately narrower than `review_output`: no disclaimer, no
    replacement text, no regeneration request. This decides only whether a
    fragment may be shown — never what the reply is.
    """
    reasons = find_blocked_reasons(sentence)
    unsupported = [] if reasons else unsupported_numbers(sentence, ledger)

    return SentenceVerdict(
        text=sentence,
        separator="",
        ok=not reasons and not unsupported,
        reasons=reasons,
        unsupported=unsupported,
    )


class SentenceGate:
    """Incremental `review_output`, one settled sentence at a time.

    A **release gate**, not a replacement guardrail: it decides when a fragment
    may leave the server; `review_output` still decides what the reply *is*.
    The two stay consistent because the gate is sentence-equivalent to the batch
    check, so it can never be the more permissive of the two — a sentence cannot
    be released and then blessed away by a looser final pass.

    Both checks are already sentence-scoped (`find_blocked_reasons` splits then
    matches per fragment; every `NumberToken` carries its own sentence and
    context), which is the only reason this is sound. `tests/test_sentence_gate.py`
    pins that equivalence.

    The subtlety is knowing when a fragment is *settled*: a boundary match that
    runs to the end of the buffer can still grow — `"\\n"` into `"\\n\\n"`,
    `". "` into `".  "` — so only a match with text after it is final.
    """

    def __init__(self, ledger: Ledger) -> None:
        self._ledger = ledger
        self._buffer = ""

    def feed(self, delta: str) -> list[SentenceVerdict]:
        """Absorb a chunk of model output; return whatever sentences it completed."""
        self._buffer += delta
        verdicts: list[SentenceVerdict] = []

        while True:
            match = _SENTENCES.search(self._buffer)
            if match is None or match.end() >= len(self._buffer):
                # No boundary yet, or one that could still grow.
                break
            fragment = self._buffer[: match.start()]
            separator = self._buffer[match.start() : match.end()]
            self._buffer = self._buffer[match.end() :]
            verdicts.append(self._judge(fragment, separator))

        return verdicts

    def flush(self) -> list[SentenceVerdict]:
        """Judge whatever is left once the stream ends."""
        remainder, self._buffer = self._buffer, ""
        if not remainder:
            return []

        # Send the tail back through the batch splitter so a trailing delimiter
        # is handled exactly as `_SENTENCES.split` would have handled it.
        pieces = _SENTENCES.split(remainder)
        return [self._judge(piece, "") for piece in pieces]

    def _judge(self, fragment: str, separator: str) -> SentenceVerdict:
        if not fragment.strip():
            return SentenceVerdict(text=fragment, separator=separator, ok=True)
        verdict = review_sentence(fragment, self._ledger)
        return SentenceVerdict(
            text=fragment,
            separator=separator,
            ok=verdict.ok,
            reasons=verdict.reasons,
            unsupported=verdict.unsupported,
        )


def review_output(
    text: str,
    ledger: Ledger | None = None,
    allow_regeneration: bool = True,
) -> GuardrailVerdict:
    """Run every guardrail over the model's final reply.

    Advice violations replace the reply wholesale — the reasoning that led there
    is suspect too. Number violations ask the loop to regenerate once; if it
    can't (no budget, or the retry failed too), the reply is withheld in favour
    of a ledger-built summary.
    """
    ledger = ledger if ledger is not None else Ledger()

    blocked_reasons = find_blocked_reasons(text)
    if blocked_reasons:
        return GuardrailVerdict(
            text=with_disclaimer(BLOCKED_REPLACEMENT),
            blocked=True,
            reasons=blocked_reasons,
        )

    unsupported = unsupported_numbers(text, ledger)
    if unsupported:
        listed = ", ".join(unsupported)
        if allow_regeneration:
            return GuardrailVerdict(
                text=text,
                regenerate_requested=True,
                unsupported=unsupported,
                reasons=[f"figures not grounded in tool output: {listed}"],
            )
        return GuardrailVerdict(
            text=with_disclaimer(ungrounded_fallback(ledger)),
            blocked=True,
            unsupported=unsupported,
            reasons=[f"withheld; figures not grounded in tool output: {listed}"],
        )

    return GuardrailVerdict(text=with_disclaimer(text))
