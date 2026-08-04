from pydantic import BaseModel, Field

from app.domain.financial_profile import FinancialProfile
from app.simulation.monthly import MonthState, simulate_month
from app.simulation.shocks import Shock


class MonthlyAdjustments(BaseModel):
    """What changes about a profile for one simulated month."""

    incomeOverrideCents: int | None = None
    expenseDeltaCents: int = 0
    shocks: list[Shock] = Field(default_factory=list)


class MonthResult(BaseModel):
    """Snapshot of state after a single simulated month."""

    monthIndex: int
    state: MonthState


class SimulationResult(BaseModel):
    """Full trajectory across N simulated months."""

    months: list[MonthResult]


def run_months(
    profile: FinancialProfile,
    start: MonthState,
    months: int,
    schedule: dict[int, MonthlyAdjustments] | None = None,
) -> SimulationResult:
    """
    Advance `months` months from `start`, applying any adjustments
    scheduled for a given month index (0-based). Returns the state
    after each month.
    """
    schedule = schedule or {}
    state = start
    results: list[MonthResult] = []

    for month_index in range(months):
        adjustments = schedule.get(month_index, MonthlyAdjustments())
        state = simulate_month(
            profile,
            state,
            shocks=adjustments.shocks,
            income_override_cents=adjustments.incomeOverrideCents,
            expense_delta_cents=adjustments.expenseDeltaCents,
        )
        results.append(MonthResult(monthIndex=month_index, state=state))

    return SimulationResult(months=results)
