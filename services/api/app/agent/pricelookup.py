"""Look up a real-world price on the web, and nothing else.

This is the only place in the codebase that fetches a number from outside. It is
deliberately narrow: it returns a price and where the price came from. It never
multiplies, never touches a profile, and never decides anything.

That narrowness is what keeps ARCHITECTURE.md's rule intact. A looked-up gas
price is not the same kind of fact as an engine-computed breaking point -- it is
an *input*, sourced from a third party, and possibly wrong. So it arrives with a
citation attached, it is offered to the user for confirmation before it is
written anywhere, and the arithmetic that turns it into a monthly cost happens in
Python (`app.agent.tools.commute_cost`), not in the model's head.

Determinism: once a looked-up value has been confirmed into the profile, the
simulation over that profile is as deterministic as it ever was. What is not
reproducible is the lookup itself -- gas cost what it costs on the day.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from time import monotonic
from typing import Any

logger = logging.getLogger(__name__)

#: Prices move slowly relative to a conversation. Re-searching on every turn
#: would cost a web search per message and give the user a slightly different
#: number each time they asked, which reads as the tool being unreliable.
CACHE_TTL_SECONDS = 60 * 60 * 6

_cache: dict[str, tuple[float, PriceQuote]] = {}


@dataclass(frozen=True)
class PriceQuote:
    """A price, in cents, and where it came from."""

    amount_cents: int
    unit: str
    source_name: str
    source_url: str
    as_of: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "amountCents": self.amount_cents,
            "unit": self.unit,
            "sourceName": self.source_name,
            "sourceUrl": self.source_url,
            "asOf": self.as_of,
        }


class PriceLookupError(RuntimeError):
    """The lookup could not produce a usable, cited price."""


_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["amountCents", "unit", "sourceName", "sourceUrl", "asOf"],
    "properties": {
        "amountCents": {
            "type": "integer",
            "description": "The price in integer cents. $3.71 per gallon is 371.",
        },
        "unit": {"type": "string", "description": "What one unit is, e.g. 'gallon'."},
        "sourceName": {"type": "string"},
        "sourceUrl": {"type": "string"},
        "asOf": {
            "type": ["string", "null"],
            "description": "Date the figure applies to, if the source states one.",
        },
    },
}

_INSTRUCTIONS = """\
You look up one current price and report it exactly as published.

Rules:
- Search the web. Do not answer from memory; prices change.
- Report the figure the source states. Do not average, adjust, or round it to
  something tidier.
- Give the price in integer cents for ONE unit.
- Cite the specific page you took it from.
- If you cannot find a credible current figure, say so rather than estimating."""


def _client():
    """Imported lazily so a missing key only breaks the feature that needs it."""
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise PriceLookupError("OPENAI_API_KEY is not configured.")
    return OpenAI(api_key=api_key)


def lookup_price(query: str, *, cache_key: str | None = None) -> PriceQuote:
    """Search the web for one current price.

    `query` is a plain-English description of the price wanted, e.g.
    "average price of regular gasoline per gallon in Charlotte, NC".
    """
    key = cache_key or query.strip().lower()
    hit = _cache.get(key)
    if hit is not None and monotonic() - hit[0] < CACHE_TTL_SECONDS:
        return hit[1]

    model = os.environ.get("OPENAI_MODEL", "gpt-5.6-luna")

    try:
        response = _client().responses.create(
            model=model,
            instructions=_INSTRUCTIONS,
            input=query,
            tools=[{"type": "web_search"}],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "price_quote",
                    "schema": _SCHEMA,
                    "strict": True,
                }
            },
        )
    except Exception as error:  # noqa: BLE001 - surfaced to the model as data
        logger.warning("price lookup failed: %s", error)
        raise PriceLookupError(str(error)) from error

    text = (response.output_text or "").strip()
    if not text:
        raise PriceLookupError("The search returned no usable figure.")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise PriceLookupError("The search result was not valid JSON.") from error

    amount = payload.get("amountCents")
    if not isinstance(amount, int) or amount <= 0:
        raise PriceLookupError("The search did not return a positive price.")

    # A price without a source is exactly the kind of unattributable number this
    # module exists to avoid producing.
    source_url = (payload.get("sourceUrl") or "").strip()
    if not source_url:
        raise PriceLookupError("The search returned a price with no source.")

    quote = PriceQuote(
        amount_cents=amount,
        unit=(payload.get("unit") or "unit").strip(),
        source_name=(payload.get("sourceName") or "web search").strip(),
        source_url=source_url,
        as_of=payload.get("asOf"),
    )

    _cache[key] = (monotonic(), quote)
    return quote


def clear_cache() -> None:
    """For tests, and for a future 'refresh this price' action."""
    _cache.clear()
