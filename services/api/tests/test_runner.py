from app.domain.financial_profile import FinancialProfile
from app.simulation.baseline import compute_baseline
from app.simulation.monthly import MonthState
from app.simulation.runner import MonthlyAdjustments, run_months
from app.simulation.shocks import Shock


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


def test_no_shocks_grows_by_buffer_each_month() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    baseline = compute_baseline(profile)
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)

    result = run_months(profile, start, months=6)

    assert len(result.months) == 6
    for i, month_result in enumerate(result.months):
        assert month_result.monthIndex == i
    expected_final_cash = 200_000 + 6 * baseline.monthlyBufferCents
    assert result.months[-1].state.cashCents == expected_final_cash


def test_shock_in_single_scheduled_month() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    baseline = compute_baseline(profile)
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)
    schedule = {
        2: MonthlyAdjustments(shocks=[Shock(name="car_repair", costCents=75_000)])
    }

    result = run_months(profile, start, months=4, schedule=schedule)

    # Month 0 and 1 unaffected (normal buffer growth)
    assert result.months[0].state.cashCents == 200_000 + baseline.monthlyBufferCents
    assert result.months[1].state.cashCents == 200_000 + 2 * baseline.monthlyBufferCents
    # Month 2 dips by the shock on top of normal buffer growth
    assert (
        result.months[2].state.cashCents
        == 200_000 + 3 * baseline.monthlyBufferCents - 75_000
    )
    # Month 3 resumes normal growth from the post-shock balance
    assert (
        result.months[3].state.cashCents
        == result.months[2].state.cashCents + baseline.monthlyBufferCents
    )


def test_shock_spills_onto_credit_card_and_persists() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    baseline = compute_baseline(profile)
    start = MonthState(cashCents=0, creditCardBalanceCents=0)
    schedule = {
        0: MonthlyAdjustments(shocks=[Shock(name="medical_bill", costCents=1_000_000)])
    }

    result = run_months(profile, start, months=2, schedule=schedule)

    # Month 0: buffer isn't enough to cover the shock, deficit goes to credit
    month0 = result.months[0].state
    assert month0.cashCents == 0
    expected_deficit = 1_000_000 - baseline.monthlyBufferCents
    assert month0.creditCardBalanceCents == expected_deficit

    # Month 1: no new shock, credit card balance carries forward unchanged
    # while normal buffer accumulates as cash
    month1 = result.months[1].state
    assert month1.creditCardBalanceCents == expected_deficit
    assert month1.cashCents == baseline.monthlyBufferCents


def test_zero_months_returns_empty_trajectory() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)

    result = run_months(profile, start, months=0)

    assert result.months == []
