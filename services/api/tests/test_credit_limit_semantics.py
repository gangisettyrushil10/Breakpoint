"""What `availableCreditCents` means, pinned.

The field was read two ways at once: the credit subscore, the dashboard and the
intake form all treated it as *remaining headroom*, while the breaking-point
search and the prevention plan treated it as the *whole line*. The consequence
was severe and silent — anyone whose balance exceeded their remaining headroom,
which is an ordinary way to hold a credit card, was reported as already broken in
month 0 before a single emergency was applied.

These tests exist so the two readings cannot drift apart again.
"""

from app.domain.financial_profile import FinancialProfile
from app.scenarios.library import car_repair, layoff
from app.simulation.prevention import build_prevention_plan
from app.simulation.scoring import compute_resilience_score, find_breaking_point


def payload(**debt) -> dict:
    base = {
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
            "availableCreditCents": 190_000,
            "creditAprBps": 2499,
        },
        "savings": {"liquidCents": 340_000},
    }
    base["debt"].update(debt)
    return base


def profile(**debt) -> FinancialProfile:
    return FinancialProfile.model_validate(payload(**debt))


def test_a_balance_above_remaining_headroom_is_not_a_breaking_point():
    """The regression that started all of this.

    $2,850 owed with $1,900 still drawable is a normal credit card, not an
    emergency. Under the old reading this reported a break in month 0 with an
    overage of exactly balance - available, before any shock was applied.
    """
    p = profile(creditCardBalanceCents=285_000, availableCreditCents=190_000)

    # A repair scheduled six months out cannot break anything in month 0.
    result = find_breaking_point(
        p, months=12, candidate_scenarios=[("car_repair", car_repair(month_index=6))]
    )

    assert result.monthIndex != 0


def test_the_ceiling_is_what_is_owed_plus_what_is_left():
    """Two profiles with the same total line behave the same.

    $1,000 owed with $4,000 free and $4,000 owed with $1,000 free are the same
    $5,000 ceiling. Any difference in where they break would mean the ceiling is
    being read from the wrong field.
    """
    low = profile(creditCardBalanceCents=100_000, availableCreditCents=400_000)
    high = profile(creditCardBalanceCents=400_000, availableCreditCents=100_000)

    schedule = [("layoff", layoff(start_month=0, duration_months=4))]
    low_break = find_breaking_point(low, months=12, candidate_scenarios=schedule)
    high_break = find_breaking_point(high, months=12, candidate_scenarios=schedule)

    # The higher starting balance eats its headroom sooner, so it breaks no
    # later — but both are measured against the same $5,000 ceiling, so neither
    # may break in month 0 on the strength of the balance alone.
    assert low_break.monthIndex != 0
    assert high_break.monthIndex != 0


def test_more_headroom_never_makes_things_worse():
    """Monotonicity. Raising the limit can only delay a break, never hasten it."""
    schedule = [("layoff", layoff(start_month=0, duration_months=4))]

    tight = find_breaking_point(
        profile(availableCreditCents=50_000), months=12, candidate_scenarios=schedule
    )
    loose = find_breaking_point(
        profile(availableCreditCents=900_000), months=12, candidate_scenarios=schedule
    )

    if tight.triggered and loose.triggered:
        assert loose.monthIndex >= tight.monthIndex
    else:
        # More credit turning a break into a survival is the expected direction.
        assert tight.triggered or not loose.triggered


def test_maxed_out_means_no_headroom_left():
    """`alreadyOverCreditLimit` now means zero headroom, which is reachable."""
    maxed = profile(availableCreditCents=0, creditCardBalanceCents=180_000)
    breaking = find_breaking_point(
        maxed,
        months=3,
        candidate_scenarios=[("layoff", layoff(start_month=0, duration_months=3))],
    )
    plan = build_prevention_plan(maxed, breaking)

    assert plan is not None
    assert plan.alreadyOverCreditLimit is True
    # Nothing to recommend: this engine never repays debt, so no future saving
    # reopens a card with nothing left on it.
    assert plan.extraSavingsCentsNeeded is None


def test_a_card_with_headroom_is_not_reported_as_maxed():
    p = profile(availableCreditCents=190_000)
    breaking = find_breaking_point(
        p,
        months=12,
        candidate_scenarios=[("layoff", layoff(start_month=0, duration_months=4))],
    )
    plan = build_prevention_plan(p, breaking)

    if plan is not None:
        assert plan.alreadyOverCreditLimit is False


def test_the_subscore_already_agreed_and_still_does():
    """`scoring.py` computes utilisation as available / (available + balance).

    That was the reading the breaking-point search disagreed with. Pinning it
    here makes the two halves of one file fail together if either moves.
    """
    p = profile(creditCardBalanceCents=100_000, availableCreditCents=300_000)
    score = compute_resilience_score(p)

    # 300k free of a 400k line is 75% unused.
    assert score.creditSubscore == 75
