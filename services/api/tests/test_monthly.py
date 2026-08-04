from app.domain.financial_profile import FinancialProfile
from app.simulation.baseline import compute_baseline
from app.simulation.monthly import MonthState, simulate_month
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


def test_month_with_no_shocks() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)

    end = simulate_month(profile, start, shocks=[])

    # 200_000 + 435_000 - 325_000 = 310_000
    assert end.cashCents == 310_000
    assert end.creditCardBalanceCents == 0


def test_month_with_car_repair_shock() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)
    shocks = [Shock(name="car_repair", costCents=75_000)]

    end = simulate_month(profile, start, shocks=shocks)

    # 310_000 - 75_000 = 235_000
    assert end.cashCents == 235_000
    assert end.creditCardBalanceCents == 0


def test_huge_shock_pushes_deficit_to_credit_card() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    start = MonthState(cashCents=200_000, creditCardBalanceCents=0)
    shocks = [Shock(name="medical_bill", costCents=500_000)]

    end = simulate_month(profile, start, shocks=shocks)

    # 200_000 + 435_000 - 325_000 - 500_000 = -190_000 → cash 0, CC 190_000
    assert end.cashCents == 0
    assert end.creditCardBalanceCents == 190_000


def test_month_uses_baseline_total_expenses() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    baseline = compute_baseline(profile)
    start = MonthState(
        cashCents=profile.savings.liquidCents,
        creditCardBalanceCents=0,
    )

    end = simulate_month(profile, start)

    expected_cash = (
        profile.savings.liquidCents
        + profile.income.monthlyTakeHomeCents
        - baseline.totalExpensesCents
    )
    assert end.cashCents == expected_cash
