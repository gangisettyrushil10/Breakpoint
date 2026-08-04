from app.domain.financial_profile import FinancialProfile
from app.scenarios.library import car_repair, layoff, merge_schedules, rent_hike
from app.simulation.baseline import compute_baseline
from app.simulation.monthly import MonthState
from app.simulation.runner import run_months


def valid_profile_payload() -> dict:
    return {
        "schemaVersion": 1,
        "currency": "USD",
        "location": {
            "city": "Dallas",
            "state": "TX",
            "postalCode": "75201",
        },
        "household": {
            "dependents": 0,
            "jobStability": "stable",
        },
        "income": {
            "monthlyTakeHomeCents": 435000,
            "payFrequency": "biweekly",
        },
        "expenses": {
            "rentCents": 155000,
            "utilitiesCents": 22000,
            "groceriesCents": 45000,
            "transportationCents": 20000,
            "insuranceCents": 18000,
            "subscriptionsCents": 5000,
            "discretionaryCents": 30000,
            "otherEssentialCents": 0,
        },
        "debt": {
            "minimumPaymentsCents": 30000,
            "creditCardBalanceCents": 0,
            "availableCreditCents": 200000,
            "creditAprBps": 2299,
        },
        "savings": {
            "liquidCents": 200000,
        },
    }


def test_car_repair_hits_only_its_month() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    baseline = compute_baseline(profile)
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)
    schedule = car_repair(month_index=1, cost_cents=75_000)

    result = run_months(profile, start, months=3, schedule=schedule)

    assert result.months[0].state.cashCents == 200_000 + baseline.monthlyBufferCents
    assert (
        result.months[1].state.cashCents
        == 200_000 + 2 * baseline.monthlyBufferCents - 75_000
    )
    assert (
        result.months[2].state.cashCents
        == result.months[1].state.cashCents + baseline.monthlyBufferCents
    )


def test_rent_hike_reduces_buffer_for_its_duration() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    baseline = compute_baseline(profile)
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)
    schedule = rent_hike(start_month=1, duration_months=10, increase_cents=20_000)

    result = run_months(profile, start, months=3, schedule=schedule)

    hiked_buffer = baseline.monthlyBufferCents - 20_000
    assert result.months[0].state.cashCents == 200_000 + baseline.monthlyBufferCents
    assert result.months[1].state.cashCents == result.months[0].state.cashCents + hiked_buffer
    assert result.months[2].state.cashCents == result.months[1].state.cashCents + hiked_buffer


def test_layoff_zeroes_income_for_its_duration() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    baseline = compute_baseline(profile)
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)
    schedule = layoff(start_month=0, duration_months=2, replacement_income_cents=0)

    result = run_months(profile, start, months=3, schedule=schedule)

    # Month 0: no income, savings absorb part of expenses, rest to credit
    month0 = result.months[0].state
    assert month0.cashCents == 0
    assert month0.creditCardBalanceCents == baseline.totalExpensesCents - 200_000

    # Month 1: still laid off, no cash cushion left, full expenses to credit
    month1 = result.months[1].state
    assert month1.cashCents == 0
    assert (
        month1.creditCardBalanceCents
        == month0.creditCardBalanceCents + baseline.totalExpensesCents
    )

    # Month 2: back to normal income, buffer accrues again as cash
    month2 = result.months[2].state
    assert month2.cashCents == baseline.monthlyBufferCents
    assert month2.creditCardBalanceCents == month1.creditCardBalanceCents


def test_stacked_layoff_and_car_repair_in_same_month() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    baseline = compute_baseline(profile)
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)
    schedule = merge_schedules(
        layoff(start_month=0, duration_months=1, replacement_income_cents=0),
        car_repair(month_index=0, cost_cents=75_000),
    )

    result = run_months(profile, start, months=1, schedule=schedule)

    month0 = result.months[0].state
    expected_deficit = baseline.totalExpensesCents + 75_000 - 200_000
    assert month0.cashCents == 0
    assert month0.creditCardBalanceCents == expected_deficit
