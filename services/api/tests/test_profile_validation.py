import pytest
from pydantic import ValidationError

from app.domain.enums import JobStability, PayFrequency
from app.domain.financial_profile import FinancialProfile


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


def test_valid_profile_parses() -> None:
    profile = FinancialProfile.model_validate(valid_profile_payload())

    assert profile.schemaVersion == 1
    assert profile.currency == "USD"
    assert profile.income.monthlyTakeHomeCents == 435000
    assert profile.household.jobStability is JobStability.STABLE
    assert profile.income.payFrequency is PayFrequency.BIWEEKLY
    assert profile.debt.creditAprBps == 2299


def test_negative_cents_fail() -> None:
    payload = valid_profile_payload()
    payload["expenses"]["rentCents"] = -1

    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(payload)


def test_zero_take_home_fails() -> None:
    payload = valid_profile_payload()
    payload["income"]["monthlyTakeHomeCents"] = 0

    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(payload)


def test_bad_job_stability_enum_fails() -> None:
    payload = valid_profile_payload()
    payload["household"]["jobStability"] = "gig"

    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(payload)


def test_unsupported_schema_version_fails() -> None:
    payload = valid_profile_payload()
    payload["schemaVersion"] = 2

    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(payload)


def test_non_usd_currency_fails() -> None:
    payload = valid_profile_payload()
    payload["currency"] = "EUR"

    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(payload)


def test_credit_apr_out_of_range_fails() -> None:
    payload = valid_profile_payload()
    payload["debt"]["creditAprBps"] = 10001

    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(payload)


def test_missing_required_field_fails() -> None:
    payload = valid_profile_payload()
    del payload["savings"]

    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(payload)
