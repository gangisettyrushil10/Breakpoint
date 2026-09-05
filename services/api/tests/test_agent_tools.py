"""The agent's `simulate` tool must never diverge from POST /simulate.

If these fail, the chat agent and the dashboard are quoting different numbers
for the same budget — which is the one thing this product cannot do.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.agent.tools import (
    explain_score,
    patch_profile,
    plan_resilience,
    registry,
)
from app.agent.tools import (
    simulate as simulate_tool,
)
from app.domain.financial_profile import FinancialProfile
from app.main import app
from app.simulation.scoring import compute_resilience_score

client = TestClient(app)


def maya_profile_payload() -> dict:
    """The Maya Restrepo demo budget the web dashboard ships with."""
    return {
        "schemaVersion": 1,
        "currency": "USD",
        "location": {"city": "Columbus", "state": "OH", "postalCode": "43215"},
        "household": {"dependents": 0, "jobStability": "stable"},
        "income": {"monthlyTakeHomeCents": 468_000, "payFrequency": "biweekly"},
        "expenses": {
            "rentCents": 165_000,
            "utilitiesCents": 18_500,
            "groceriesCents": 52_000,
            "transportationCents": 34_000,
            "insuranceCents": 21_000,
            "subscriptionsCents": 6_800,
            "discretionaryCents": 42_000,
            "otherEssentialCents": 9_500,
        },
        "debt": {
            "minimumPaymentsCents": 64_000,
            "creditCardBalanceCents": 284_000,
            "availableCreditCents": 466_000,
            "creditAprBps": 2499,
        },
        "savings": {"liquidCents": 850_000},
    }


def maya_profile() -> FinancialProfile:
    return FinancialProfile.model_validate(maya_profile_payload())


CASES = [
    pytest.param(6, [], id="baseline-no-scenarios"),
    pytest.param(12, [], id="full-year-no-scenarios"),
    pytest.param(
        4,
        [{"type": "car_repair", "monthIndex": 2, "costCents": 240_000}],
        id="single-car-repair",
    ),
    pytest.param(
        12,
        [
            {
                "type": "layoff",
                "startMonth": 0,
                "durationMonths": 5,
                "replacementIncomeCents": 120_000,
            },
            {"type": "car_repair", "monthIndex": 3, "costCents": 240_000},
        ],
        id="stacked-layoff-plus-repair",
    ),
    pytest.param(
        6,
        [
            {
                "type": "rent_hike",
                "startMonth": 1,
                "durationMonths": 5,
                "increaseCents": 25_000,
            }
        ],
        id="rent-hike",
    ),
    pytest.param(
        3,
        [
            {
                "type": "custom_shock",
                "monthIndex": 1,
                "name": "pet_emergency",
                "costCents": 90_000,
            }
        ],
        id="custom-shock",
    ),
]


@pytest.mark.parametrize("months,scenarios", CASES)
def test_tool_matches_simulate_route(months: int, scenarios: list[dict]) -> None:
    route_response = client.post(
        "/simulate",
        json={"profile": maya_profile_payload(), "months": months, "scenarios": scenarios},
    )
    assert route_response.status_code == 200

    tool_payload = simulate_tool.handle(
        maya_profile(), {"months": months, "scenarios": scenarios}
    )

    assert tool_payload["ok"] is True
    assert tool_payload["result"] == route_response.json()


def test_tool_matches_explicit_breaking_point_discovery() -> None:
    arguments = {
        "months": 12,
        "scenarios": [],
        "discoverBreakingPoint": True,
    }
    route_response = client.post(
        "/simulate", json={"profile": maya_profile_payload(), **arguments}
    )

    tool_payload = simulate_tool.handle(maya_profile(), arguments)

    assert route_response.status_code == 200
    assert tool_payload["result"] == route_response.json()
    assert tool_payload["discoverBreakingPoint"] is True


def test_tool_defaults_to_six_months() -> None:
    payload = simulate_tool.handle(maya_profile(), {})

    assert payload["ok"] is True
    assert payload["months"] == 6
    assert len(payload["result"]["simulation"]["months"]) == 6


def test_tool_reports_bad_arguments_instead_of_raising() -> None:
    payload = simulate_tool.handle(
        maya_profile(),
        {"months": 3, "scenarios": [{"type": "car_repair", "monthIndex": 9}]},
    )

    assert payload["ok"] is False
    assert payload["error"] == "invalid_arguments"


def test_tool_rejects_unknown_scenario_type() -> None:
    payload = simulate_tool.handle(
        maya_profile(),
        {"months": 3, "scenarios": [{"type": "asteroid_strike", "monthIndex": 0}]},
    )

    assert payload["ok"] is False


@pytest.mark.parametrize(
    "tool,arguments",
    [
        (simulate_tool, {"months": 99}),
        (simulate_tool, {"scenarios": [{"type": "nope"}]}),
        (patch_profile, {"income": {"monthlyTakeHomeCents": -1}}),
        (patch_profile, {"savings": {"crypto": 1}}),
    ],
)
def test_error_payloads_are_json_serialisable(tool, arguments: dict) -> None:
    """Every tool result is JSON-encoded on its way back to the model.

    Pydantic's raw `errors()` embeds the original exception under `ctx`, which
    is not serialisable — regression guard for that.
    """
    payload = tool.handle(maya_profile(), arguments)

    assert payload["ok"] is False
    json.dumps(payload)


def test_tool_input_schema_is_object_shaped() -> None:
    schema = simulate_tool.input_schema()

    assert schema["type"] == "object"
    assert set(schema["properties"]) == {
        "months",
        "scenarios",
        "discoverBreakingPoint",
    }


def test_schema_advertises_no_months_default() -> None:
    """The model must not be handed a `months` default it can echo back.

    `_run_tools` layers the model's arguments over the server's, so an echoed
    default silently overrides the horizon the user is looking at. Seen live:
    the dashboard showed 12 months and the reply described 6, both grounded, so
    nothing downstream could catch the disagreement.
    """
    months = simulate_tool.input_schema()["properties"]["months"]

    assert "default" not in months
    # The bounds still have to reach the model.
    assert months["minimum"] == 1
    assert months["maximum"] == 12


def test_omitting_months_leaves_the_server_horizon_intact() -> None:
    """The pydantic default still applies where nothing else supplies one."""
    payload = simulate_tool.handle(maya_profile(), {"months": 12, "scenarios": []})

    assert payload["months"] == 12
    assert len(payload["result"]["simulation"]["months"]) == 12


def test_tool_definitions_are_openai_safe() -> None:
    """`oneOf`, `discriminator`, and `title` are not part of the schema subset
    OpenAI documents; `anyOf` and `$ref`/`$defs` are."""
    encoded = json.dumps(registry.tool_definitions())

    assert '"oneOf"' not in encoded
    assert '"discriminator"' not in encoded
    assert '"title"' not in encoded  # pure prompt cost, resent every call
    assert '"anyOf"' in encoded


def test_normalisation_keeps_the_scenario_discriminator_visible() -> None:
    """Dropping `discriminator` is only safe because each branch still carries
    a `const` on `type` — that's what tells the model which variant to build."""
    simulate_def = next(
        d for d in registry.tool_definitions() if d["name"] == "simulate"
    )
    schema = simulate_def["parameters"]
    branches = schema["properties"]["scenarios"]["items"]["anyOf"]

    consts = {
        schema["$defs"][branch["$ref"].split("/")[-1]]["properties"]["type"]["const"]
        for branch in branches
    }
    assert consts == {
        "car_repair",
        "medical_bill",
        "rent_hike",
        "layoff",
        "custom_shock",
    }


def test_normalisation_leaves_constraints_intact() -> None:
    normalised = registry.openai_safe_schema(
        {
            "title": "Drop me",
            "type": "object",
            "properties": {"n": {"type": "integer", "minimum": 0, "title": "N"}},
            "oneOf": [{"discriminator": "x", "type": "string"}],
        }
    )

    assert "title" not in normalised
    assert "oneOf" not in normalised
    assert normalised["anyOf"] == [{"type": "string"}]
    assert normalised["properties"]["n"] == {"type": "integer", "minimum": 0}


def test_patch_profile_merges_only_named_fields() -> None:
    profile = maya_profile()

    payload = patch_profile.handle(profile, {"savings": {"liquidCents": 100_000}})

    assert payload["ok"] is True
    updated = FinancialProfile.model_validate(payload["profile"])
    assert updated.savings.liquidCents == 100_000
    # Everything else is untouched.
    assert updated.income.monthlyTakeHomeCents == profile.income.monthlyTakeHomeCents
    assert updated.expenses.rentCents == profile.expenses.rentCents
    assert payload["changed"] == ["savings.liquidCents"]


def test_patch_profile_rejects_invalid_values() -> None:
    # The partial schema mirrors FinancialProfile's constraints, so a bad value
    # is caught at the argument boundary; `invalid_profile` is the backstop for
    # whole-profile rules the partial models can't express.
    payload = patch_profile.handle(
        maya_profile(), {"income": {"monthlyTakeHomeCents": -1}}
    )

    assert payload["ok"] is False
    assert payload["error"] == "invalid_arguments"


def test_patch_profile_rejects_unknown_fields() -> None:
    payload = patch_profile.handle(maya_profile(), {"savings": {"crypto": 100}})

    assert payload["ok"] is False
    assert payload["error"] == "invalid_arguments"


def test_patch_profile_rejects_empty_patch() -> None:
    payload = patch_profile.handle(maya_profile(), {})

    assert payload["ok"] is False
    assert payload["error"] == "empty_patch"


def test_explain_score_returns_the_weighted_formula() -> None:
    payload = explain_score.handle(maya_profile(), {})

    assert payload["ok"] is True
    assert payload["score"] == simulate_tool.run_simulate(
        maya_profile()
    ).resilience.score
    assert [component["weightPercent"] for component in payload["components"]] == [
        50,
        30,
        20,
    ]
    assert payload["weakestComponent"] in {"runway", "buffer", "credit"}
    assert payload["writesProfile"] is False


def test_plan_resilience_finds_minimum_verified_pathways() -> None:
    profile = maya_profile()
    payload = plan_resilience.handle(profile, {"targetScore": 60})

    assert payload["ok"] is True
    assert payload["currentScore"] < payload["targetScore"]
    assert payload["writesProfile"] is False
    assert profile == maya_profile()

    for pathway in payload["pathways"]:
        if not pathway["feasible"]:
            continue
        required = pathway["requiredCents"]
        assert pathway["resultingScore"] >= 60
        if required >= 100:
            changed = plan_resilience._profile_with(profile, pathway["id"], required - 100)
            assert compute_resilience_score(changed).score < 60


def test_plan_resilience_limits_cuts_to_flexible_spending() -> None:
    profile = maya_profile()
    payload = plan_resilience.handle(profile, {"targetScore": 100})
    flexible_path = next(
        pathway
        for pathway in payload["pathways"]
        if pathway["id"] == "flexible_cut"
    )

    assert flexible_path["feasible"] is False
    assert flexible_path["maximumTestedCents"] == (
        profile.expenses.subscriptionsCents + profile.expenses.discretionaryCents
    )
