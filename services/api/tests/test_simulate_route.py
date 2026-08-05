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


def test_simulate_with_typed_scenario_applies_it() -> None:
    body = {
        "profile": valid_profile_payload(),
        "months": 4,
        "scenarios": [{"type": "car_repair", "monthIndex": 2, "costCents": 75_000}],
    }

    response = client.post("/simulate", json=body)

    assert response.status_code == 200
    data = response.json()
    months = data["simulation"]["months"]
    hit_month = months[2]["state"]
    prior_month = months[1]["state"]
    assert hit_month["cashCents"] < prior_month["cashCents"] + 110_000


def test_simulate_applies_custom_scenario_amount_not_the_old_default() -> None:
    body = {
        "profile": valid_profile_payload(),
        "months": 2,
        "scenarios": [{"type": "rent_hike", "startMonth": 0, "durationMonths": 2, "increaseCents": 100_000}],
    }

    response = client.post("/simulate", json=body)

    assert response.status_code == 200
    data = response.json()
    month0 = data["simulation"]["months"][0]["state"]
    # buffer is 110_000; a 100_000 hike (not the old hardcoded 20_000 default)
    # should leave only ~10_000 growth, not the old ~90_000
    assert month0["cashCents"] == 200_000 + (110_000 - 100_000)


def test_simulate_custom_shock_uses_its_own_name_and_cost() -> None:
    body = {
        "profile": valid_profile_payload(),
        "months": 2,
        "scenarios": [
            {"type": "custom_shock", "monthIndex": 0, "name": "pet_emergency", "costCents": 40_000}
        ],
    }

    response = client.post("/simulate", json=body)

    assert response.status_code == 200
    data = response.json()
    month0 = data["simulation"]["months"][0]["state"]
    assert month0["cashCents"] == 200_000 + 110_000 - 40_000


def test_simulate_rejects_unknown_scenario_type() -> None:
    body = {
        "profile": valid_profile_payload(),
        "months": 3,
        "scenarios": [{"type": "asteroid_strike", "monthIndex": 0, "costCents": 1}],
    }

    response = client.post("/simulate", json=body)

    assert response.status_code == 422


def test_simulate_rejects_scenario_month_out_of_range() -> None:
    body = {
        "profile": valid_profile_payload(),
        "months": 3,
        "scenarios": [{"type": "car_repair", "monthIndex": 5, "costCents": 75_000}],
    }

    response = client.post("/simulate", json=body)

    assert response.status_code == 422


def test_simulate_rejects_invalid_profile() -> None:
    bad_profile = valid_profile_payload()
    bad_profile["income"]["monthlyTakeHomeCents"] = -100

    response = client.post("/simulate", json={"profile": bad_profile, "months": 3})

    assert response.status_code == 422
