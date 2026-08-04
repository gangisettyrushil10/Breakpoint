from typing import Callable

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


def _default_car_repair(months: int) -> Schedule:
    return car_repair(month_index=months // 2)


def _default_medical_bill(months: int) -> Schedule:
    return medical_bill(month_index=months // 2)


def _default_rent_hike(months: int) -> Schedule:
    return rent_hike(start_month=1, duration_months=max(months - 1, 1), increase_cents=20_000)


def _default_layoff(months: int) -> Schedule:
    return layoff(start_month=0, duration_months=min(2, months), replacement_income_cents=0)


SCENARIO_PRESETS: dict[str, Callable[[int], Schedule]] = {
    "car_repair": _default_car_repair,
    "medical_bill": _default_medical_bill,
    "rent_hike": _default_rent_hike,
    "layoff": _default_layoff,
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
