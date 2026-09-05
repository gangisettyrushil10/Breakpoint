"""The gate must be exactly as strict as the batch guardrail, one sentence early.

Streaming is only safe because `find_blocked_reasons` and `unsupported_numbers`
are already sentence-scoped: each splits the reply and evaluates fragments
independently, and every `NumberToken` carries its own sentence and context. So
a fragment can be judged the moment it is complete, and released only if clean.

That claim is what these tests defend. If any of them fail, streaming is
unsound and `SentenceGate` must not be wired to the wire.
"""

import random
import string

import pytest
from test_agent_tools import maya_profile

from app.agent.grounding import Ledger, build_ledger, unsupported_numbers
from app.agent.guardrails import (
    _SENTENCES,
    SentenceGate,
    find_blocked_reasons,
    review_sentence,
)
from app.agent.tools.simulate import run_simulate


def ledger_for(months: int = 6) -> Ledger:
    return build_ledger(simulate_results=[run_simulate(maya_profile(), months=months)])


def chunk(text: str, sizes: list[int]) -> list[str]:
    """Split `text` into consecutive pieces of the given sizes."""
    pieces, index = [], 0
    for size in sizes:
        if index >= len(text):
            break
        pieces.append(text[index : index + size])
        index += size
    if index < len(text):
        pieces.append(text[index:])
    return pieces


def gate_fragments(text: str, sizes: list[int], ledger: Ledger) -> list[str]:
    gate = SentenceGate(ledger)
    seen: list[str] = []
    for piece in chunk(text, sizes):
        seen.extend(v.text for v in gate.feed(piece))
    seen.extend(v.text for v in gate.flush())
    return seen


# --------------------------------------------------------------------------
# Splitting: the gate must reproduce _SENTENCES.split() under any chunking
# --------------------------------------------------------------------------

SPLIT_CASES = [
    "One sentence only.",
    "Two sentences. Here is the second.",
    "Trailing whitespace after this.   ",
    "No terminal punctuation at all",
    "Bullet list:\n- first item\n- second item",
    "Double newline break.\n\nNew paragraph here.",
    "Questions? Yes! And ellipsis... then more.",
    "Money $1,250.00 mid sentence. And 2.3 months after.",
    "A\n\n\nB.\n",
    "",
    "   ",
    "\n\n",
]


@pytest.mark.parametrize("text", SPLIT_CASES)
def test_gate_splits_identically_to_the_batch_regex(text: str) -> None:
    """One chunk at a time is still the same split as the whole string."""
    expected = [f for f in _SENTENCES.split(text) if f.strip()]
    actual = [f for f in gate_fragments(text, [len(text) or 1], ledger_for()) if f.strip()]

    assert actual == expected


@pytest.mark.parametrize("text", SPLIT_CASES)
def test_gate_splitting_is_independent_of_chunk_boundaries(text: str) -> None:
    """A boundary that straddles a delimiter must not change the result.

    This is the case that breaks a naive implementation: "\\n" can still grow
    into "\\n\\n", and ". " into ".  ", so a boundary at the very end of the
    buffer is not yet settled.
    """
    expected = [f for f in _SENTENCES.split(text) if f.strip()]
    random.seed(hash(text) & 0xFFFF)

    for _ in range(40):
        sizes = [random.randint(1, 4) for _ in range(len(text) + 2)]
        actual = [f for f in gate_fragments(text, sizes, ledger_for()) if f.strip()]
        assert actual == expected, f"chunking {sizes[:6]}… changed the split"


def test_fuzz_random_text_splits_identically() -> None:
    alphabet = string.ascii_letters + " .!?\n$,0123456789"
    random.seed(20260811)

    for _ in range(300):
        text = "".join(random.choice(alphabet) for _ in range(random.randint(0, 60)))
        expected = [f for f in _SENTENCES.split(text) if f.strip()]
        sizes = [random.randint(1, 5) for _ in range(len(text) + 2)]
        actual = [f for f in gate_fragments(text, sizes, ledger_for()) if f.strip()]
        assert actual == expected, f"diverged on {text!r}"


def test_fragments_plus_separators_reconstruct_the_original() -> None:
    """`_SENTENCES.split` consumes its delimiter, so the gate has to carry it.

    Without this the client would render "A.B." for "A. B.".
    """
    text = "First one. Second one!\n\nThird one?\nFourth."
    gate = SentenceGate(ledger_for())
    verdicts = [*gate.feed(text), *gate.flush()]

    assert "".join(v.text + v.separator for v in verdicts) == text


# --------------------------------------------------------------------------
# Verdicts: per-fragment judgements must union to the batch judgement
# --------------------------------------------------------------------------

BLOCKED_TEXTS = [
    "You should take out a payday loan.",
    "Your score is fine. One option is a title loan to bridge the gap.",
    "A payday loan is your fastest way out.",
    "You could skip rent this month.",
    "What is your social security number?",
]

CLEAN_TEXTS = [
    "I can't recommend a payday loan — they usually pull the breaking point closer.",
    "A score of 80 or above is generally considered resilient.",
    "Payday loans typically carry 400% APR.",
]


@pytest.mark.parametrize("text", BLOCKED_TEXTS + CLEAN_TEXTS)
def test_blocked_reasons_match_the_batch_check(text: str) -> None:
    ledger = ledger_for()
    gate = SentenceGate(ledger)
    verdicts = [*gate.feed(text), *gate.flush()]

    from_gate = {reason for v in verdicts for reason in v.reasons}

    assert from_gate == set(find_blocked_reasons(text))


@pytest.mark.parametrize("text", BLOCKED_TEXTS)
def test_blocked_sentences_are_never_released(text: str) -> None:
    gate = SentenceGate(ledger_for())
    verdicts = [*gate.feed(text), *gate.flush()]

    assert any(not v.ok for v in verdicts), "a blocked reply passed the gate"


@pytest.mark.parametrize("text", CLEAN_TEXTS)
def test_clean_sentences_are_released(text: str) -> None:
    gate = SentenceGate(ledger_for())
    verdicts = [*gate.feed(text), *gate.flush()]

    assert all(v.ok for v in verdicts), [v.reasons + v.unsupported for v in verdicts]


def test_ungrounded_figures_match_the_batch_check() -> None:
    ledger = ledger_for()
    text = (
        "Your resilience score is 50. Your runway is 47.5 months. "
        "Your monthly buffer is $552.00."
    )
    gate = SentenceGate(ledger)
    verdicts = [*gate.feed(text), *gate.flush()]

    from_gate = [u for v in verdicts for u in v.unsupported]

    assert from_gate == unsupported_numbers(text, ledger)
    # The invented runway is caught; the two real figures are not.
    assert from_gate == ["47.5 months"]


def test_an_empty_ledger_makes_every_figure_unsupported() -> None:
    """The worst failure — answering without simulating — needs no special case."""
    gate = SentenceGate(Ledger())
    verdicts = [*gate.feed("Your score is 91 and your runway is 4.2 months."), *gate.flush()]

    assert any(not v.ok for v in verdicts)


def test_review_sentence_is_pure_over_one_fragment() -> None:
    """No disclaimer, no replacement text — the gate only decides release."""
    verdict = review_sentence("You should take out a payday loan.", Ledger())

    assert verdict.ok is False
    assert verdict.reasons == ["recommended a high-cost credit product"]
    assert "educational projection" not in verdict.text
