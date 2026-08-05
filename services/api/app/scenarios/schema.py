from typing import Annotated, Literal

from pydantic import BaseModel, Field

from app.scenarios.library import Schedule, car_repair, layoff, medical_bill, rent_hike
from app.simulation.runner import MonthlyAdjustments
from app.simulation.shocks import Shock


class CarRepairInput(BaseModel):
    type: Literal["car_repair"]
    monthIndex: int = Field(ge=0)
    costCents: int = Field(default=75_000, ge=0)


class MedicalBillInput(BaseModel):
    type: Literal["medical_bill"]
    monthIndex: int = Field(ge=0)
    costCents: int = Field(default=150_000, ge=0)


class RentHikeInput(BaseModel):
    type: Literal["rent_hike"]
    startMonth: int = Field(ge=0)
    durationMonths: int = Field(ge=1)
    increaseCents: int = Field(ge=0)


class LayoffInput(BaseModel):
    type: Literal["layoff"]
    startMonth: int = Field(ge=0)
    durationMonths: int = Field(ge=1)
    replacementIncomeCents: int = Field(default=0, ge=0)


class CustomShockInput(BaseModel):
    """Any one-time hardship that doesn't fit a named preset."""

    type: Literal["custom_shock"]
    monthIndex: int = Field(ge=0)
    name: str = Field(min_length=1)
    costCents: int = Field(ge=0)


ScenarioInput = Annotated[
    CarRepairInput | MedicalBillInput | RentHikeInput | LayoffInput | CustomShockInput,
    Field(discriminator="type"),
]


def scenario_last_month(scenario: ScenarioInput) -> int:
    """The last month index this scenario touches, for bounds checking."""
    if isinstance(scenario, (CarRepairInput, MedicalBillInput, CustomShockInput)):
        return scenario.monthIndex
    return scenario.startMonth + scenario.durationMonths - 1


def resolve_scenario(scenario: ScenarioInput) -> Schedule:
    """Builds a Schedule from a request-supplied scenario, using its own
    parameters instead of the SCENARIO_PRESETS defaults."""
    if isinstance(scenario, CarRepairInput):
        return car_repair(month_index=scenario.monthIndex, cost_cents=scenario.costCents)
    if isinstance(scenario, MedicalBillInput):
        return medical_bill(month_index=scenario.monthIndex, cost_cents=scenario.costCents)
    if isinstance(scenario, RentHikeInput):
        return rent_hike(
            start_month=scenario.startMonth,
            duration_months=scenario.durationMonths,
            increase_cents=scenario.increaseCents,
        )
    if isinstance(scenario, LayoffInput):
        return layoff(
            start_month=scenario.startMonth,
            duration_months=scenario.durationMonths,
            replacement_income_cents=scenario.replacementIncomeCents,
        )
    return {
        scenario.monthIndex: MonthlyAdjustments(
            shocks=[Shock(name=scenario.name, costCents=scenario.costCents)]
        )
    }
