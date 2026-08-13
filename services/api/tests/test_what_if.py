"""Pricing a permanent change without committing to it.

Three things are under test. That the comparison is honest — both sides run the
same engine over the same horizon, and the deltas are the tool's arithmetic
rather than the model's. That nothing is written: the entire value of asking
"what would this cost me?" depends on being able to ask without it becoming true.
And that the deltas reach the grounding ledger, because a computed difference the
model is forbidden from deriving itself would otherwise be withheld by the
guardrail — the exact trap the commute lookup hit.
"""

import pytest

from app.agent.grounding import build_ledger, facts_from_what_if
from app.agent.tools import what_if
from app.agent.tools.registry import REGISTRY, dispatch
from app.domain.financial_profile import FinancialProfile


def payload() -> dict:
    return {
        "schemaVersion": 1,
        "currency": "USD",
        "location": {"city": "Charlotte", "state": "NC", "postalCode": "28205"},
        "household": {"dependents": 0, "jobStability": "stable"},
        "income": {"monthlyTakeHomeCents": 412_000, "payFrequency": "biweekly"},
        "expenses": {
            "rentCents": 169_000,
            "utilitiesCents": 14_500,
            "groceriesCents": 42_000,
            "transportationCents": 29_500,
            "insuranceCents": 16_500,
            "subscriptionsCents": 6_500,
            "discretionaryCents": 31_000,
            "otherEssentialCents": 8_000,
        },
        "debt": {
            "minimumPaymentsCents": 26_000,
            "creditCardBalanceCents": 285_000,
            "availableCreditCents": 550_000,
            "creditAprBps": 2499,
        },
        "savings": {"liquidCents": 340_000},
    }


@pytest.fixture
def profile() -> FinancialProfile:
    return FinancialProfile.model_validate(payload())


def worse(profile: FinancialProfile, extra_fuel_cents: int = 4_000) -> dict:
    """Fuel going up is the motivating example, so it is the default case."""
    return what_if.handle(
        profile,
        {
            "change": {
                "expenses": {
                    "transportationCents": (
                        profile.expenses.transportationCents + extra_fuel_cents
                    )
                }
            }
        },
    )


class TestTheComparison:
    def test_a_worse_budget_scores_lower(self, profile):
        result = worse(profile)

        assert result["ok"] is True
        assert result["score"]["after"] < result["score"]["before"]
        assert result["score"]["delta"] < 0

    def test_the_delta_is_the_difference_between_the_two_sides(self, profile):
        # The model may not subtract these itself, so the tool has to be right.
        result = worse(profile)

        assert (
            result["score"]["delta"]
            == result["score"]["after"] - result["score"]["before"]
        )
        assert (
            result["monthlyBufferCents"]["delta"]
            == result["monthlyBufferCents"]["after"]
            - result["monthlyBufferCents"]["before"]
        )

    def test_spending_more_leaves_less_over(self, profile):
        result = worse(profile, extra_fuel_cents=10_000)

        assert result["monthlyBufferCents"]["delta"] == -10_000

    def test_a_better_budget_scores_higher(self, profile):
        result = what_if.handle(
            profile, {"change": {"savings": {"liquidCents": 1_000_000}}}
        )

        assert result["score"]["delta"] > 0
        assert result["runwayMonths"]["delta"] > 0

    def test_no_change_is_no_difference(self, profile):
        """An empty change must be a true no-op, not a rounding wobble."""
        result = what_if.handle(profile, {"change": {}})

        assert result["score"]["delta"] == 0
        assert result["monthlyBufferCents"]["delta"] == 0
        assert result["runwayMonths"]["delta"] == 0

    def test_both_sides_face_the_same_shocks(self, profile):
        """Otherwise the comparison would be measuring two different questions."""
        result = what_if.handle(
            profile,
            {
                "change": {"expenses": {"rentCents": 200_000}},
                "scenarios": [
                    {"type": "layoff", "startMonth": 0, "durationMonths": 3}
                ],
                "months": 12,
            },
        )

        assert result["ok"] is True
        # A materially worse budget under the same layoff cannot break later.
        before = result["breakingPoint"]["before"]
        after = result["breakingPoint"]["after"]
        if before["triggered"] and after["triggered"]:
            assert after["monthIndex"] <= before["monthIndex"]


class TestRelativeChanges:
    """"Rent goes up $200" is a movement, not a new total.

    The absolute form alone produced a real failure: asked what a $200 rent rise
    would do, the model sent `rentCents: 20000` — setting rent *to* $200 — and
    reported that the budget improved dramatically. It cannot fix that itself
    either, because adding $200 to the current rent is arithmetic it is forbidden
    from doing. So the movement has to be expressible, and the server does the sum.
    """

    def test_an_increase_adds_to_what_is_there(self, profile):
        result = what_if.handle(
            profile, {"changeBy": {"expenses": {"rentCents": 20_000}}}
        )

        assert result["ok"] is True
        # $200 more rent is exactly $200 less left over.
        assert result["monthlyBufferCents"]["delta"] == -20_000
        assert result["score"]["delta"] < 0

    def test_a_decrease_is_a_negative_amount(self, profile):
        result = what_if.handle(
            profile, {"changeBy": {"expenses": {"subscriptionsCents": -6_500}}}
        )

        assert result["ok"] is True
        assert result["monthlyBufferCents"]["delta"] == 6_500
        assert result["score"]["delta"] >= 0

    def test_a_raise_helps(self, profile):
        result = what_if.handle(
            profile, {"changeBy": {"income": {"monthlyTakeHomeCents": 30_000}}}
        )

        assert result["monthlyBufferCents"]["delta"] == 30_000
        assert result["score"]["delta"] > 0

    def test_relative_and_absolute_agree(self, profile):
        """Same destination by either route, so the two forms cannot diverge."""
        relative = what_if.handle(
            profile, {"changeBy": {"expenses": {"rentCents": 20_000}}}
        )
        absolute = what_if.handle(
            profile,
            {"change": {"expenses": {"rentCents": profile.expenses.rentCents + 20_000}}},
        )

        assert relative["score"] == absolute["score"]
        assert relative["monthlyBufferCents"] == absolute["monthlyBufferCents"]

    def test_cutting_more_than_exists_is_rejected(self, profile):
        """Cancelling $200 of a $65 subscription bill has no sensible answer."""
        result = what_if.handle(
            profile, {"changeBy": {"expenses": {"subscriptionsCents": -20_000}}}
        )

        assert result["ok"] is False
        assert result["error"] == "invalid_change"

    def test_sending_neither_form_is_an_error(self, profile):
        result = what_if.handle(profile, {"scenarios": []})

        assert result["ok"] is False
        assert result["error"] == "invalid_arguments"

    def test_a_relative_change_still_saves_nothing(self, profile):
        before = profile.model_dump()
        what_if.handle(profile, {"changeBy": {"expenses": {"rentCents": 50_000}}})

        assert profile.model_dump() == before


class TestItChangesNothing:
    def test_the_profile_is_untouched(self, profile):
        before = profile.model_dump()
        worse(profile, extra_fuel_cents=50_000)

        assert profile.model_dump() == before

    def test_it_does_not_return_a_profile_to_save(self, profile):
        result = worse(profile)

        assert result["writesProfile"] is False
        assert "profile" not in result

    def test_it_is_registered_as_non_mutating(self):
        assert REGISTRY[what_if.TOOL_NAME].mutates_profile is False

    def test_repeated_questions_do_not_accumulate(self, profile):
        """Trying three ideas in a row must compare each against the original."""
        first = worse(profile, extra_fuel_cents=10_000)
        second = worse(profile, extra_fuel_cents=10_000)

        assert first["score"] == second["score"]
        assert first["monthlyBufferCents"] == second["monthlyBufferCents"]


class TestBadInput:
    def test_an_impossible_change_is_data_not_a_crash(self, profile):
        result = what_if.handle(
            profile, {"change": {"expenses": {"rentCents": -100}}}
        )

        assert result["ok"] is False
        assert result["error"] in {"invalid_arguments", "invalid_change"}

    def test_a_scenario_past_the_horizon_is_rejected(self, profile):
        result = what_if.handle(
            profile,
            {
                "change": {},
                "months": 3,
                "scenarios": [{"type": "car_repair", "monthIndex": 9}],
            },
        )

        assert result["ok"] is False

    def test_it_reaches_the_model_through_the_registry(self, profile):
        result = dispatch(
            what_if.TOOL_NAME,
            profile,
            {"change": {"expenses": {"subscriptionsCents": 0}}},
        )

        assert result["ok"] is True


class TestGrounding:
    """Without these the guardrail withholds the answer to the question asked."""

    def test_both_sides_and_the_delta_are_quotable(self, profile):
        result = worse(profile)
        ledger = build_ledger(what_if_results=[result])

        assert ledger.supports(float(result["score"]["before"]), "score")
        assert ledger.supports(float(result["score"]["after"]), "score")
        assert ledger.supports_any_kind(float(result["score"]["delta"]))

    def test_the_drop_is_quotable_as_a_magnitude(self, profile):
        """"Costs you two points" is the natural sentence, and it drops the sign."""
        result = worse(profile)
        ledger = build_ledger(what_if_results=[result])

        assert ledger.supports_any_kind(abs(float(result["score"]["delta"])))

    def test_the_new_buffer_is_quotable_as_money(self, profile):
        result = worse(profile)
        ledger = build_ledger(what_if_results=[result])

        assert ledger.supports(result["monthlyBufferCents"]["after"] / 100, "money")

    def test_a_score_the_tool_never_produced_is_not_quotable(self, profile):
        result = worse(profile)
        ledger = build_ledger(what_if_results=[result])

        invented = float(result["score"]["before"]) + 17
        assert not ledger.supports(invented, "score")

    def test_a_failed_comparison_grounds_nothing(self, profile):
        result = what_if.handle(
            profile, {"change": {"expenses": {"rentCents": -100}}}
        )

        assert facts_from_what_if(result) == []
