from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


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


def test_health_still_works() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_simulate_with_no_scenarios_returns_full_shape() -> None:
    body = {"profile": valid_profile_payload(), "months": 3, "scenarios": []}

    response = client.post("/simulate", json=body)

    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) == {
        "baseline",
        "resilience",
        "simulation",
        "breakingPoint",
        "preventionPlan",
    }
    assert data["baseline"]["totalExpensesCents"] == 325_000
    assert len(data["simulation"]["months"]) == 3
    assert "score" in data["resilience"]
    assert "triggered" in data["breakingPoint"]


def test_simulate_with_named_scenarios_applies_them() -> None:
    body = {
        "profile": valid_profile_payload(),
        "months": 4,
        "scenarios": ["car_repair"],
    }

    response = client.post("/simulate", json=body)

    assert response.status_code == 200
    data = response.json()
    months = data["simulation"]["months"]
    # car_repair defaults to hitting the middle month (months // 2 = 2)
    hit_month = months[2]["state"]
    prior_month = months[1]["state"]
    assert hit_month["cashCents"] < prior_month["cashCents"] + 110_000


def test_simulate_rejects_unknown_scenario_name() -> None:
    body = {
        "profile": valid_profile_payload(),
        "months": 3,
        "scenarios": ["asteroid_strike"],
    }

    response = client.post("/simulate", json=body)

    assert response.status_code == 422


def test_simulate_rejects_invalid_profile() -> None:
    bad_profile = valid_profile_payload()
    bad_profile["income"]["monthlyTakeHomeCents"] = -100

    response = client.post("/simulate", json={"profile": bad_profile, "months": 3})

    assert response.status_code == 422
