import pytest

from app.domain.financial_profile import FinancialProfile
from app.simulation.baseline import compute_baseline


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


def test_dallas_baseline_numbers() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())
    result = compute_baseline(profile)

    assert result.fixedExpensesCents == 203_000
    assert result.essentialExpensesCents == 290_000
    assert result.totalExpensesCents == 325_000
    assert result.monthlyBufferCents == 110_000
    assert result.runwayMonths == pytest.approx(200_000 / 290_000)


def test_zero_essentials_runway_is_none() -> None:
    payload = valid_profile_payload()
    payload["expenses"] = {
        "rentCents": 0,
        "utilitiesCents": 0,
        "groceriesCents": 0,
        "transportationCents": 0,
        "insuranceCents": 0,
        "subscriptionsCents": 0,
        "discretionaryCents": 0,
        "otherEssentialCents": 0,
    }
    payload["debt"]["minimumPaymentsCents"] = 0

    profile = FinancialProfile.model_validate(payload)
    result = compute_baseline(profile)

    assert result.essentialExpensesCents == 0
    assert result.runwayMonths is None


def test_overspender_has_negative_buffer() -> None:
    payload = valid_profile_payload()
    payload["income"]["monthlyTakeHomeCents"] = 100_000

    profile = FinancialProfile.model_validate(payload)
    result = compute_baseline(profile)

    assert result.monthlyBufferCents < 0
