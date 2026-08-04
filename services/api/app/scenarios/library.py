from app.simulation.runner import MonthlyAdjustments
from app.simulation.shocks import Shock

Schedule = dict[int, MonthlyAdjustments]


def car_repair(month_index: int, cost_cents: int = 75_000) -> Schedule:
    """One-time repair bill hitting a single month."""
    return {
        month_index: MonthlyAdjustments(
            shocks=[Shock(name="car_repair", costCents=cost_cents)]
        )
    }


def medical_bill(month_index: int, cost_cents: int = 150_000) -> Schedule:
    """One-time medical bill hitting a single month."""
    return {
        month_index: MonthlyAdjustments(
            shocks=[Shock(name="medical_bill", costCents=cost_cents)]
        )
    }


def rent_hike(start_month: int, duration_months: int, increase_cents: int) -> Schedule:
    """A rent increase that lasts duration_months, starting at start_month."""
    return {
        month: MonthlyAdjustments(expenseDeltaCents=increase_cents)
        for month in range(start_month, start_month + duration_months)
    }


def layoff(
    start_month: int,
    duration_months: int,
    replacement_income_cents: int = 0,
) -> Schedule:
    """Loss of the normal paycheck for duration_months, starting at start_month."""
    return {
        month: MonthlyAdjustments(incomeOverrideCents=replacement_income_cents)
        for month in range(start_month, start_month + duration_months)
    }


def merge_schedules(*schedules: Schedule) -> Schedule:
    """
    Combine schedules (e.g. to stack scenarios). Expense deltas add up,
    shocks concatenate, and an income override from a later schedule
    replaces an earlier one for the same month.
    """
    merged: Schedule = {}

    for schedule in schedules:
        for month, adjustment in schedule.items():
            existing = merged.get(month, MonthlyAdjustments())
            merged[month] = MonthlyAdjustments(
                incomeOverrideCents=(
                    adjustment.incomeOverrideCents
                    if adjustment.incomeOverrideCents is not None
                    else existing.incomeOverrideCents
                ),
                expenseDeltaCents=existing.expenseDeltaCents + adjustment.expenseDeltaCents,
                shocks=existing.shocks + adjustment.shocks,
            )

    return merged
