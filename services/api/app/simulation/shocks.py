from pydantic import BaseModel, Field


class Shock(BaseModel):
    """One-time emergency cost applied inside a simulated month."""

    name: str = Field(min_length=1)
    costCents: int = Field(ge=0)
