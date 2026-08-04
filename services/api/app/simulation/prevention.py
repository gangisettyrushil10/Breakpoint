import math

from pydantic import BaseModel

from app.domain.financial_profile import FinancialProfile
from app.simulation.scoring import BreakingPoint


class PreventionPlan(BaseModel):
    """
    Two deterministic levers that would have avoided a triggered breaking
    point: extra starting savings, or a permanent monthly spending cut.
    Both are derived directly from BreakingPoint.overageCents — no search,
    no guessing.

    Neither lever can be computed if the profile's credit card balance
    already exceeds its available credit before any shock — this engine
    never repays existing debt, it only prevents *new* deficits, so no
    amount of future savings/cuts can undo an already-exceeded limit.
    """

    alreadyOverCreditLimit: bool
    extraSavingsCentsNeeded: int | None
    monthlyCutCentsNeeded: int | None
    cuttableMonthlyCents: int
    monthlyCutFeasible: bool | None


def build_prevention_plan(
    profile: FinancialProfile, breaking_point: BreakingPoint
) -> PreventionPlan | None:
    """None if breaking_point wasn't triggered — there's nothing to prevent."""
    if not breaking_point.triggered:
        return None

    overage = breaking_point.overageCents
    month_index = breaking_point.monthIndex
    assert overage is not None and month_index is not None

    cuttable = profile.expenses.discretionaryCents + profile.expenses.subscriptionsCents
    already_over_limit = profile.debt.creditCardBalanceCents > profile.debt.availableCreditCents

    if already_over_limit:
        return PreventionPlan(
            alreadyOverCreditLimit=True,
            extraSavingsCentsNeeded=None,
            monthlyCutCentsNeeded=None,
            cuttableMonthlyCents=cuttable,
            monthlyCutFeasible=None,
        )

    months_elapsed = month_index + 1
    monthly_cut_needed = math.ceil(overage / months_elapsed)

    return PreventionPlan(
        alreadyOverCreditLimit=False,
        extraSavingsCentsNeeded=overage,
        monthlyCutCentsNeeded=monthly_cut_needed,
        cuttableMonthlyCents=cuttable,
        monthlyCutFeasible=monthly_cut_needed <= cuttable,
    )
