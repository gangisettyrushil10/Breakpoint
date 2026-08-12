"""Guardrails: catch numbers we didn't compute, block advice we won't give.

Every test in the first two sections is a regression test for a bug found by
audit and reproduced against the real engine. The literal strings are the ones
that actually failed.
"""

import pytest

from app.agent.grounding import build_ledger
from app.agent.guardrails import (
    DISCLAIMER,
    UNGROUNDED_BARE,
    find_blocked_reasons,
    review_output,
)
from app.agent.tools.simulate import run_simulate
from app.scenarios.schema import LayoffInput
from tests.test_agent_tools import maya_profile

# Truth for the Maya profile: score 50 (subscores 39/59/62), runway 2.335 months,
# buffer $552.00, and no breaking point over 6 unstressed months.
RESULT = run_simulate(maya_profile(), months=6)
LEDGER = build_ledger([RESULT])
EMPTY = build_ledger([])

# A profile that does break, for breaking-point claims.
BROKEN = run_simulate(
    maya_profile(),
    months=12,
    scenarios=[
        LayoffInput(
            type="layoff", startMonth=0, durationMonths=5, replacementIncomeCents=0
        )
    ],
)
BROKEN_LEDGER = build_ledger([BROKEN])


def withheld(verdict) -> bool:
    """The reply was not shown to the user."""
    return verdict.blocked and bool(verdict.unsupported)


# ---------------------------------------------------------------------------
# Ungrounded numbers
# ---------------------------------------------------------------------------


def test_flags_invented_numbers_when_no_tool_ran() -> None:
    """The worst case: the model skips the tool and invents everything.

    Previously unchecked entirely — correction was gated on a tool result
    existing, so a reply built from nothing sailed through.
    """
    verdict = review_output(
        "Your score of 88 and runway of 14.0 months look great.",
        EMPTY,
        allow_regeneration=False,
    )

    assert withheld(verdict)
    assert "88" not in verdict.text
    assert UNGROUNDED_BARE in verdict.text


def test_flags_an_invented_dollar_figure() -> None:
    verdict = review_output(
        "Your monthly buffer is $3,000 a month.", LEDGER, allow_regeneration=False
    )

    assert withheld(verdict)
    assert "$3,000" in verdict.unsupported


def test_flags_an_invented_breaking_point() -> None:
    """The engine found no breaking point; claiming one is the worst kind of
    fabrication, because it's the product's headline number."""
    assert RESULT.breakingPoint.triggered is False

    verdict = review_output(
        "Your breaking point hits in month 2.", LEDGER, allow_regeneration=False
    )

    assert withheld(verdict)


def test_flags_the_wrong_breaking_point_month() -> None:
    verdict = review_output(
        "Your budget breaks in month 9.", BROKEN_LEDGER, allow_regeneration=False
    )

    assert withheld(verdict)


@pytest.mark.parametrize(
    "claim",
    [
        "Your resilience score: 91 is solid.",  # colon with no space
        "You scored 91 out of 100.",
        "Your resilience is a 91/100.",
        "You have about 9.4 months of runway.",  # noun order reversed
        "Your savings would last 9.4 months.",
    ],
)
def test_catches_phrasings_that_used_to_evade(claim: str) -> None:
    verdict = review_output(claim, LEDGER, allow_regeneration=False)

    assert withheld(verdict), claim


def test_a_subscore_does_not_validate_a_resilience_score_claim() -> None:
    """62 is the credit subscore, not the resilience score."""
    assert RESULT.resilience.creditSubscore == 62
    assert RESULT.resilience.score != 62

    verdict = review_output(
        "Your resilience score is 62.", LEDGER, allow_regeneration=False
    )

    assert withheld(verdict)


def test_requests_regeneration_before_withholding() -> None:
    verdict = review_output("Your monthly buffer is $3,000.", LEDGER)

    assert verdict.regenerate_requested is True
    assert verdict.blocked is False
    assert verdict.unsupported == ["$3,000"]


# ---------------------------------------------------------------------------
# Correct text must survive untouched
# ---------------------------------------------------------------------------


def test_does_not_rewrite_a_decimal_score() -> None:
    """The old corrector turned "61.5" into "50.5" — a number nothing produced."""
    verdict = review_output(
        "Your resilience score of 61.5 is middling.", LEDGER, allow_regeneration=False
    )

    assert "50.5" not in verdict.text
    assert withheld(verdict)


def test_leaves_generic_scale_statements_alone() -> None:
    """The old corrector turned this true sentence into a false one."""
    verdict = review_output(
        "A score of 80 or above is considered resilient.", LEDGER
    )

    assert verdict.blocked is False
    assert verdict.regenerate_requested is False
    assert "80" in verdict.text


@pytest.mark.parametrize(
    "claim",
    [
        "Your resilience score of 50 is middling.",
        "You have about 2.3 months of runway.",
        "Your monthly buffer is $552 a month.",
        "The runway subscore is 39.",
        "Over the next 6 months your cash holds.",
        "In month 4 your cash is still positive.",
        "3 to 6 months of emergency savings is the usual rule of thumb.",
        "Payday loans typically carry an APR around 400%.",
    ],
)
def test_grounded_and_generic_text_passes_clean(claim: str) -> None:
    verdict = review_output(claim, LEDGER)

    assert verdict.blocked is False, claim
    assert verdict.regenerate_requested is False, claim


def test_numbers_the_user_supplied_are_quotable() -> None:
    ledger = build_ledger(
        [RESULT],
        tool_arguments=[{"scenarios": [{"monthIndex": 3, "costCents": 240_000}]}],
        user_messages=["what happens if a $2,400 repair hits?"],
    )

    verdict = review_output(
        "The $2,400 repair you asked about lands in month 3.", ledger
    )

    assert verdict.blocked is False
    assert verdict.regenerate_requested is False


# ---------------------------------------------------------------------------
# Advice blocklist
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        "You should take out a payday loan to cover the gap.",
        "I'd recommend a cash-advance app for the shortfall.",
        "One option is a 401k withdrawal to cover the repair.",
        "You should tap your retirement account to cover the repair.",
        "A payday loan is your fastest way to cover this.",  # product leads
        "A title loan could bridge the gap until payday.",
        "Take out a payday loan to get through the month.",  # imperative
    ],
)
def test_blocks_high_cost_credit_recommendations(reply: str) -> None:
    verdict = review_output(reply, LEDGER)

    assert verdict.blocked is True, reply
    assert "payday" not in verdict.text.lower()


@pytest.mark.parametrize(
    "reply",
    [
        "To free up cash, you could skip your rent payment in month three.",
        "You should just not pay rent this month.",
    ],
)
def test_blocks_skipping_an_essential_payment(reply: str) -> None:
    assert review_output(reply, LEDGER).blocked is True, reply


@pytest.mark.parametrize(
    "reply",
    [
        "What is your bank account number so I can check?",
        "Just paste your online banking login here.",
    ],
)
def test_blocks_requests_for_credentials(reply: str) -> None:
    assert review_output(reply, LEDGER).blocked is True, reply


@pytest.mark.parametrize(
    "reply",
    [
        "Do not take out a payday loan.",
        "Avoid taking out a payday loan — the APR is punishing.",
        "You should not skip your rent payment.",
        "If you are considering a payday loan, here is why it is expensive.",
        "You cannot afford a payday loan at that APR.",
        "Never consider a payday loan for this.",
        "A payday loan would be a bad idea here.",
    ],
)
def test_warning_against_a_product_is_not_recommending_it(reply: str) -> None:
    """The system prompt tells the model to explain why these are expensive.

    The old rules blocked it for doing so — prompt and guardrail were in direct
    conflict, and the guardrail won.
    """
    assert find_blocked_reasons(reply) == [], reply


def test_explaining_cost_without_recommending_passes() -> None:
    verdict = review_output(
        "Payday loans typically carry an APR around 400%, which would push your "
        "breaking point closer rather than further out.",
        LEDGER,
    )

    assert verdict.blocked is False
    assert "400%" in verdict.text


# ---------------------------------------------------------------------------
# Disclaimer
# ---------------------------------------------------------------------------


def test_appends_disclaimer_once() -> None:
    verdict = review_output(
        "Your resilience score of 50 leaves little slack.", LEDGER
    )

    assert verdict.text.count(DISCLAIMER) == 1


def test_does_not_double_up_on_an_existing_disclaimer() -> None:
    verdict = review_output(
        "Here's the projection. This is not financial advice, just the math.", LEDGER
    )

    assert DISCLAIMER not in verdict.text
