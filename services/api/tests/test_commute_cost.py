"""The web-backed commute estimate.

Two things are being protected here. The first is arithmetic: the model must
never be the thing that multiplies miles by a fuel price, so the tool has to
produce the monthly figure itself and produce it correctly. The second is
grounding: the resulting numbers must reach the ledger, because otherwise the
guardrail withholds the very reply that shows the user their estimate.

No test in this file touches the network. `lookup_price` is substituted, which is
also the point of it living in its own module.
"""

import pytest

from app.agent import pricelookup
from app.agent.grounding import build_ledger, facts_from_lookup
from app.agent.pricelookup import PriceLookupError, PriceQuote
from app.agent.tools import commute_cost
from app.agent.tools.registry import REGISTRY, dispatch
from app.domain.financial_profile import FinancialProfile


def profile_payload() -> dict:
    return {
        "schemaVersion": 1,
        "currency": "USD",
        "location": {"city": "Charlotte", "state": "NC", "postalCode": "28205"},
        "household": {"dependents": 0, "jobStability": "stable"},
        "income": {"monthlyTakeHomeCents": 412_000, "payFrequency": "biweekly"},
        "expenses": {
            "rentCents": 169_000,
            "utilitiesCents": 14_500,
            "groceriesCents": 42_000,
            "transportationCents": 29_500,
            "insuranceCents": 16_500,
            "subscriptionsCents": 6_500,
            "discretionaryCents": 31_000,
            "otherEssentialCents": 8_000,
        },
        "debt": {
            "minimumPaymentsCents": 26_000,
            "creditCardBalanceCents": 285_000,
            "availableCreditCents": 550_000,
            "creditAprBps": 2499,
        },
        "savings": {"liquidCents": 340_000},
    }


@pytest.fixture
def profile() -> FinancialProfile:
    return FinancialProfile.model_validate(profile_payload())


QUOTE = PriceQuote(
    amount_cents=371,
    unit="gallon",
    source_name="AAA Fuel Prices",
    source_url="https://gasprices.aaa.com/?state=NC",
    as_of="2026-08-12",
)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Every test in this file gets a fixed quote instead of a web search."""
    monkeypatch.setattr(commute_cost, "lookup_price", lambda *a, **k: QUOTE)
    pricelookup.clear_cache()


def test_computes_the_monthly_cost_itself(profile):
    result = commute_cost.handle(
        profile, {"milesEachWay": 24, "daysPerWeek": 5, "milesPerGallon": 28}
    )

    # 24 * 2 * 5 * (52/12) = 1040 miles; / 28 mpg = 37.14 gal; * $3.71 = $137.80.
    # Worked by hand so a refactor that quietly changes the formula is caught.
    assert result["ok"] is True
    assert result["monthlyCostCents"] == 13_780
    assert result["assumptions"]["monthlyMiles"] == 1040.0


def test_uses_a_month_of_52_over_12_weeks(profile):
    """Four weeks a month would understate every commute by about 7%."""
    result = commute_cost.handle(profile, {"milesEachWay": 10, "daysPerWeek": 5})
    four_week_miles = 10 * 2 * 5 * 4

    assert result["assumptions"]["monthlyMiles"] > four_week_miles


def test_reports_an_assumed_mpg_as_assumed(profile):
    assumed = commute_cost.handle(profile, {"milesEachWay": 24})
    stated = commute_cost.handle(profile, {"milesEachWay": 24, "milesPerGallon": 28})

    assert assumed["assumptions"]["milesPerGallonWasAssumed"] is True
    assert assumed["assumptions"]["milesPerGallon"] == commute_cost.DEFAULT_MPG
    assert stated["assumptions"]["milesPerGallonWasAssumed"] is False


def test_carries_the_citation_through(profile):
    result = commute_cost.handle(profile, {"milesEachWay": 24})

    assert result["fuelPrice"]["sourceUrl"] == QUOTE.source_url
    assert result["fuelPrice"]["amountCents"] == 371


def test_never_writes_to_the_profile(profile):
    before = profile.model_dump()
    result = commute_cost.handle(profile, {"milesEachWay": 24})

    assert result["writesProfile"] is False
    assert result["isEstimate"] is True
    assert "profile" not in result
    assert profile.model_dump() == before


def test_is_not_registered_as_profile_mutating():
    """A confirm-first tool that could write would defeat the confirmation."""
    assert REGISTRY[commute_cost.TOOL_NAME].mutates_profile is False


def test_a_failed_lookup_is_data_not_an_exception(profile, monkeypatch):
    def boom(*args, **kwargs):
        raise PriceLookupError("no credible figure found")

    monkeypatch.setattr(commute_cost, "lookup_price", boom)
    result = commute_cost.handle(profile, {"milesEachWay": 24})

    assert result["ok"] is False
    assert result["error"] == "price_lookup_failed"
    # The model needs somewhere to go other than inventing a number.
    assert "suggestion" in result


def test_rejects_a_nonsense_commute(profile):
    result = commute_cost.handle(profile, {"milesEachWay": -4})

    assert result["ok"] is False
    assert result["error"] == "invalid_arguments"


def test_reaches_the_model_through_the_registry(profile):
    result = dispatch(commute_cost.TOOL_NAME, profile, {"milesEachWay": 24})

    assert result["ok"] is True


class TestGrounding:
    """Without these, the guardrail withholds the reply showing the estimate."""

    def test_the_monthly_cost_is_quotable(self, profile):
        result = commute_cost.handle(profile, {"milesEachWay": 24, "milesPerGallon": 28})
        ledger = build_ledger(lookup_results=[result])

        assert ledger.supports(137.80, "money")

    def test_the_fuel_price_is_quotable(self, profile):
        result = commute_cost.handle(profile, {"milesEachWay": 24})
        ledger = build_ledger(lookup_results=[result])

        assert ledger.supports(3.71, "money")

    def test_a_figure_the_tool_never_produced_is_not_quotable(self, profile):
        result = commute_cost.handle(profile, {"milesEachWay": 24, "milesPerGallon": 28})
        ledger = build_ledger(lookup_results=[result])

        # The whole point: a plausible-looking commute cost that came from
        # nowhere must still be caught.
        assert not ledger.supports(210.00, "money")

    def test_a_failed_lookup_grounds_nothing(self, profile, monkeypatch):
        monkeypatch.setattr(
            commute_cost,
            "lookup_price",
            lambda *a, **k: (_ for _ in ()).throw(PriceLookupError("down")),
        )
        result = commute_cost.handle(profile, {"milesEachWay": 24})

        assert facts_from_lookup(result) == []
