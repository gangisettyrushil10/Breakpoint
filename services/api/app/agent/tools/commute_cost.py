"""The `estimate_commute_cost` tool: turn "24 miles each way" into dollars.

The division of labour matters more here than anywhere else in the agent:

* the **user** supplies the facts about their life (distance, days, the car);
* the **web** supplies one price, with a citation;
* **this module** does every multiplication;
* the **model** does none of it -- it reads the result out and asks whether it
  looks right.

If the model were left to work out `24 * 2 * 5 * 4.33 / 28 * 3.71` it would be
inventing a figure that lands in someone's budget and moves their breaking
point. That is precisely the failure ARCHITECTURE.md's non-negotiable rule
exists to prevent, so the arithmetic lives in Python and comes back as a tool
result the grounding ledger can vouch for.

Nothing here writes to the profile. The model is instructed to show the estimate
and wait for a yes before calling `patch_profile`.
"""

from pydantic import BaseModel, Field, ValidationError

from app.agent.pricelookup import PriceLookupError, lookup_price
from app.agent.tools.errors import validation_detail
from app.domain.financial_profile import FinancialProfile

TOOL_NAME = "estimate_commute_cost"

TOOL_DESCRIPTION = """\
Work out what someone's driving commute costs per month, using the current local
petrol/gas price looked up from the web.

Call this when the user describes their commute in distance rather than dollars
("I drive about 24 miles each way", "it's an hour up the interstate"). You supply
what they told you about the journey; the server looks up the fuel price for
their area and does all the arithmetic.

Do NOT work the cost out yourself, and do not guess a fuel price -- you have no
way to know today's. If the user already knows what they spend on fuel, just use
`patch_profile` with their figure instead.

This tool does not change the budget. Show the user the estimate and what it was
based on, ask whether it looks right, and only call `patch_profile` once they
agree."""

#: 52 weeks / 12 months. Using 4 would quietly understate every commute by 7%.
WEEKS_PER_MONTH = 52 / 12

#: US average for light-duty vehicles. Only used when the user has not said what
#: they drive, and always reported back so the assumption is visible.
DEFAULT_MPG = 24.4


class CommuteCostInput(BaseModel):
    """What the user told you about the journey. The profile supplies location."""

    milesEachWay: float = Field(
        gt=0,
        le=500,
        description="One-way distance of the commute in miles.",
    )
    daysPerWeek: float = Field(
        default=5,
        gt=0,
        le=7,
        description="How many days a week they make the trip. Defaults to 5.",
    )
    milesPerGallon: float | None = Field(
        default=None,
        gt=0,
        le=150,
        description=(
            "The car's fuel economy, if the user said. Leave unset if they did "
            "not -- a national average is used and reported back as an assumption."
        ),
    )


def input_schema() -> dict:
    return CommuteCostInput.model_json_schema()


def handle(profile: FinancialProfile, arguments: dict) -> dict:
    try:
        parsed = CommuteCostInput.model_validate(arguments or {})
    except ValidationError as error:
        return {
            "ok": False,
            "error": "invalid_arguments",
            "detail": validation_detail(error),
        }

    where = f"{profile.location.city}, {profile.location.state}".strip(", ")
    query = (
        f"What is the current average price of a gallon of regular gasoline in "
        f"{where or 'the United States'}?"
    )

    try:
        quote = lookup_price(query, cache_key=f"gas:{where.lower()}")
    except PriceLookupError as error:
        # Returned as data so the model can fall back to asking the user what
        # they spend, rather than the whole turn failing.
        return {
            "ok": False,
            "error": "price_lookup_failed",
            "detail": str(error),
            "suggestion": "Ask the user what they currently spend on fuel per month.",
        }

    mpg = parsed.milesPerGallon or DEFAULT_MPG
    monthly_miles = parsed.milesEachWay * 2 * parsed.daysPerWeek * WEEKS_PER_MONTH
    gallons = monthly_miles / mpg
    monthly_cost_cents = round(gallons * quote.amount_cents)

    return {
        "ok": True,
        "monthlyCostCents": monthly_cost_cents,
        "fuelPrice": quote.as_dict(),
        # Echoed back so the model can state what the figure rests on, and so the
        # user can correct an assumption they never made.
        "assumptions": {
            "milesEachWay": parsed.milesEachWay,
            "daysPerWeek": parsed.daysPerWeek,
            "milesPerGallon": mpg,
            "milesPerGallonWasAssumed": parsed.milesPerGallon is None,
            "weeksPerMonth": round(WEEKS_PER_MONTH, 4),
            "monthlyMiles": round(monthly_miles, 1),
        },
        "isEstimate": True,
        "writesProfile": False,
        "nextStep": (
            "Show this figure with its source, say what it assumed, and ask the "
            "user to confirm before calling patch_profile."
        ),
    }
