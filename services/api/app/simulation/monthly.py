from pydantic import BaseModel, Field

from app.domain.financial_profile import FinancialProfile
from app.simulation.baseline import compute_baseline
from app.simulation.shocks import Shock


class MonthState(BaseModel):
    """Cash and credit snapshot at a point in the simulation."""

    cashCents: int
    creditCardBalanceCents: int = Field(ge=0)


def simulate_month(
    profile: FinancialProfile,
    state: MonthState,
    shocks: list[Shock] | None = None,
    income_override_cents: int | None = None,
    expense_delta_cents: int = 0,
) -> MonthState:
    """
    Advance one month: income in, normal bills out, shock costs out.
    Negative cash is moved onto the credit card; cash is floored at 0.

    income_override_cents replaces the normal monthly income for this
    month only (e.g. a layoff month). expense_delta_cents is added on
    top of the normal baseline expenses (e.g. a rent hike).
    """
    shocks = shocks or []
    baseline = compute_baseline(profile)

    cash = state.cashCents
    credit = state.creditCardBalanceCents

    income = (
        income_override_cents
        if income_override_cents is not None
        else profile.income.monthlyTakeHomeCents
    )

    cash += income
    cash -= baseline.totalExpensesCents
    cash -= expense_delta_cents
    cash -= sum(shock.costCents for shock in shocks)

    if cash < 0:
        credit += abs(cash)
        cash = 0

    return MonthState(cashCents=cash, creditCardBalanceCents=credit)
