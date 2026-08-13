from itertools import combinations

from pydantic import BaseModel

from app.domain.financial_profile import FinancialProfile
from app.scenarios.library import Schedule, merge_schedules
from app.simulation.baseline import compute_baseline
from app.simulation.monthly import MonthState
from app.simulation.runner import run_months

RUNWAY_MONTHS_FOR_FULL_SCORE = 6.0
BUFFER_MARGIN_FOR_FULL_SCORE = 0.20  # 20% of income left over each month
MAX_STACKED_SHOCKS = 3


class ResilienceScore(BaseModel):
    """0-100 explainable score, built from three weighted subscores."""

    score: int
    runwaySubscore: int
    bufferSubscore: int
    creditSubscore: int


def _clamp(value: float, low: float = 0, high: float = 100) -> int:
    return int(round(min(high, max(low, value))))


def compute_resilience_score(profile: FinancialProfile) -> ResilienceScore:
    baseline = compute_baseline(profile)
    debt = profile.debt

    if baseline.runwayMonths is None:
        runway_subscore = 100
    else:
        runway_subscore = _clamp(
            baseline.runwayMonths / RUNWAY_MONTHS_FOR_FULL_SCORE * 100
        )

    income = profile.income.monthlyTakeHomeCents
    margin = baseline.monthlyBufferCents / income
    buffer_subscore = _clamp(margin / BUFFER_MARGIN_FOR_FULL_SCORE * 100)

    total_credit = debt.availableCreditCents + debt.creditCardBalanceCents
    if total_credit == 0:
        credit_subscore = 100
    else:
        credit_subscore = _clamp(debt.availableCreditCents / total_credit * 100)

    score = _clamp(
        0.5 * runway_subscore + 0.3 * buffer_subscore + 0.2 * credit_subscore
    )

    return ResilienceScore(
        score=score,
        runwaySubscore=runway_subscore,
        bufferSubscore=buffer_subscore,
        creditSubscore=credit_subscore,
    )


class BreakingPoint(BaseModel):
    """The smallest stack of named scenarios that triggers severe risk, if any."""

    triggered: bool
    monthIndex: int | None = None
    shockCombination: list[str] = []
    overageCents: int | None = None


def _triggers_severe_risk(
    profile: FinancialProfile, schedule: Schedule, months: int
) -> tuple[int, int] | None:
    """Returns (monthIndex, overageCents) for the first month severe risk hits, or None."""
    start = MonthState(
        cashCents=profile.savings.liquidCents,
        creditCardBalanceCents=profile.debt.creditCardBalanceCents,
    )
    result = run_months(profile, start, months, schedule)

    # `availableCreditCents` is headroom — what could still be drawn — not the
    # whole line. The ceiling is therefore what is already owed plus what is
    # left, which is the same definition the credit subscore above, the
    # dashboard's `creditLimitCents`, and the intake form's own hint all use.
    #
    # Reading it as the ceiling (the previous behaviour) reported anyone whose
    # balance exceeded their remaining headroom as already broken in month 0,
    # before a single emergency was applied — a $2,850 balance with $1,900 left
    # to draw "broke" instantly. That is an ordinary way to hold a credit card,
    # not a financial emergency.
    credit_limit = (
        profile.debt.creditCardBalanceCents + profile.debt.availableCreditCents
    )

    for month_result in result.months:
        overage = month_result.state.creditCardBalanceCents - credit_limit
        if overage > 0:
            return month_result.monthIndex, overage

    return None


def find_breaking_point(
    profile: FinancialProfile,
    months: int,
    candidate_scenarios: list[tuple[str, Schedule]],
) -> BreakingPoint:
    """
    Search stacked combinations of named candidate scenarios (smallest
    stack first) for the first one that drives a month's credit-card
    balance past available credit — i.e. essentials go unpaid.
    """
    max_stack = min(MAX_STACKED_SHOCKS, len(candidate_scenarios))

    for stack_size in range(1, max_stack + 1):
        for combo in combinations(candidate_scenarios, stack_size):
            names = [name for name, _ in combo]
            merged = merge_schedules(*(schedule for _, schedule in combo))
            trigger = _triggers_severe_risk(profile, merged, months)

            if trigger is not None:
                triggered_month, overage = trigger
                return BreakingPoint(
                    triggered=True,
                    monthIndex=triggered_month,
                    shockCombination=names,
                    overageCents=overage,
                )

    return BreakingPoint(triggered=False)
