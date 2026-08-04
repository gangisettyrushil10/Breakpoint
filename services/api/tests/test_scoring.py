from app.domain.financial_profile import FinancialProfile
from app.scenarios.library import car_repair, layoff, rent_hike
from app.simulation.scoring import compute_resilience_score, find_breaking_point


def base_payload() -> dict:
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


def comfortable_profile_payload() -> dict:
    payload = base_payload()
    payload["savings"]["liquidCents"] = 3_000_000
    return payload


def thin_profile_payload() -> dict:
    payload = base_payload()
    payload["income"]["monthlyTakeHomeCents"] = 330_000
    payload["savings"]["liquidCents"] = 50_000
    payload["debt"]["availableCreditCents"] = 20_000
    payload["debt"]["creditCardBalanceCents"] = 180_000
    return payload


def test_comfortable_profile_scores_high() -> None:
    profile = FinancialProfile.model_validate(comfortable_profile_payload())

    result = compute_resilience_score(profile)

    assert result.score >= 90
    assert result.runwaySubscore == 100
    assert result.creditSubscore == 100


def test_thin_margin_profile_scores_low() -> None:
    profile = FinancialProfile.model_validate(thin_profile_payload())

    result = compute_resilience_score(profile)

    assert result.score <= 20


def test_comfortable_scores_higher_than_thin() -> None:
    comfortable = FinancialProfile.model_validate(comfortable_profile_payload())
    thin = FinancialProfile.model_validate(thin_profile_payload())

    assert compute_resilience_score(comfortable).score > compute_resilience_score(thin).score


def test_breaking_point_triggers_for_thin_profile() -> None:
    profile = FinancialProfile.model_validate(thin_profile_payload())
    candidates = [
        ("layoff", layoff(start_month=0, duration_months=3, replacement_income_cents=0)),
        ("car_repair", car_repair(month_index=0, cost_cents=75_000)),
        ("rent_hike", rent_hike(start_month=0, duration_months=3, increase_cents=20_000)),
    ]

    result = find_breaking_point(profile, months=3, candidate_scenarios=candidates)

    assert result.triggered is True
    assert result.monthIndex == 0
    assert result.shockCombination == ["layoff"]


def test_breaking_point_not_triggered_for_comfortable_profile() -> None:
    profile = FinancialProfile.model_validate(comfortable_profile_payload())
    candidates = [
        ("layoff", layoff(start_month=0, duration_months=2, replacement_income_cents=0)),
        ("car_repair", car_repair(month_index=0, cost_cents=75_000)),
        ("rent_hike", rent_hike(start_month=0, duration_months=2, increase_cents=20_000)),
    ]

    result = find_breaking_point(profile, months=3, candidate_scenarios=candidates)

    assert result.triggered is False
    assert result.monthIndex is None
    assert result.shockCombination == []
