from pydantic import BaseModel

from app.domain.financial_profile import FinancialProfile


class BaselineResult(BaseModel):
    """Receipt after the calculator has run."""

    fixedExpensesCents: int
    essentialExpensesCents: int
    totalExpensesCents: int
    monthlyBufferCents: int
    runwayMonths: float | None


def compute_baseline(profile: FinancialProfile) -> BaselineResult:
    """Compute baseline cash-flow metrics from a financial profile."""

    expenses = profile.expenses
    debt = profile.debt

    fixed = (
        expenses.rentCents
        + expenses.insuranceCents
        + debt.minimumPaymentsCents
    )

    essentials = (
        fixed
        + expenses.utilitiesCents
        + expenses.groceriesCents
        + expenses.transportationCents
        + expenses.otherEssentialCents
    )

    total = (
        essentials
        + expenses.subscriptionsCents
        + expenses.discretionaryCents
    )

    buffer = profile.income.monthlyTakeHomeCents - total

    if essentials == 0:
        runway: float | None = None
    else:
        runway = profile.savings.liquidCents / essentials

    return BaselineResult(
        fixedExpensesCents=fixed,
        essentialExpensesCents=essentials,
        totalExpensesCents=total,
        monthlyBufferCents=buffer,
        runwayMonths=runway,
    )
