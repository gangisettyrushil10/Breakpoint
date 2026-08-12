"""Which numbers is a reply allowed to contain?

The product promise is that the model never states a financial figure it didn't
get from the `simulate` tool. Enforcing that by pattern-matching claim phrasings
loses on both sides: "9.4 months of runway" evades a regex anchored on "runway
of", while "a score of 80 or above is considered resilient" gets falsely caught.

So this module inverts the problem. Instead of recognising claims, it builds a
**ledger** — the closed set of values the reply may assert — and then checks every
number in the reply against it. A number's *surface form* decides whether it's
checked ($3,000 is money-shaped, 9.4 months is months-shaped), so word order and
connector words stop mattering.

The important consequence: when the model never called `simulate`, the ledger is
empty, so every figure is unsupported. The worst failure mode needs no special
case — it's the default.
"""

import re
from dataclasses import dataclass, field
from typing import Iterable, Literal

from app.routes.simulate import SimulateResponse

Kind = Literal["money", "score", "months", "month_index", "count"]

# What a number's own shape tells us, before we look at any surrounding words.
TokenClass = Literal[
    "money",
    "months",
    "month_index",
    "score_shaped",
    "percent_owned",
    "percent_generic",
    "multiplier",
    "year",
    "ordinal",
    "list_marker",
    #: The digits are part of a product name — 401(k), 529 plan — not a figure.
    "plan_name",
    "bare",
]

ALWAYS_CHECKED: frozenset[str] = frozenset(
    {"money", "months", "month_index", "score_shaped", "percent_owned"}
)


@dataclass(frozen=True)
class Fact:
    """One value the tool actually produced, with the label it came from."""

    value: float
    kind: Kind
    label: str

    @property
    def key(self) -> str:
        """The label without its run prefix — `run0.resilience.score` -> `resilience.score`.

        Multiple simulate calls in one turn are namespaced so we can tell them
        apart, but matching cares only about which field a value came from.
        """
        return re.sub(r"^run\d+\.", "", self.label)


@dataclass
class Ledger:
    """The closed set of values a reply may assert about this user."""

    facts: list[Fact] = field(default_factory=list)
    # Numbers the user themselves said, or that we sent as tool arguments.
    # Quoting these back is legitimate and needs no simulation to support it.
    echoed: set[float] = field(default_factory=set)

    def is_empty(self) -> bool:
        return not self.facts

    def supports(self, value: float, kind: Kind, keys: set[str] | None = None) -> bool:
        """Is `value` a legitimate thing to say, read as a `kind`?"""
        if _close_to_any(value, self.echoed):
            return True
        return any(
            _matches(value, fact, kind, keys or set())
            for fact in self.facts
            if fact.kind == kind
        )

    def supports_any_kind(self, value: float) -> bool:
        """For bare integers, where we can't infer what the number means."""
        if _close_to_any(value, self.echoed):
            return True
        return any(_matches(value, fact, fact.kind, set()) for fact in self.facts)

    def summary_lines(self) -> list[str]:
        """Grounded-by-construction figures, for the fallback reply."""
        wanted = [
            ("resilience.score", "Resilience score", "{v:.0f} out of 100"),
            ("baseline.runwayMonths", "Runway", "{v:.1f} months of essentials"),
            ("baseline.monthlyBufferCents", "Monthly buffer", "${v:,.0f}"),
        ]
        by_label = {fact.key: fact for fact in self.facts}
        lines = []
        for label, title, template in wanted:
            fact = by_label.get(label)
            if fact is not None:
                lines.append(f"- {title}: {template.format(v=fact.value)}")
        return lines


def _close_to_any(value: float, values: Iterable[float]) -> bool:
    return any(abs(value - other) < 0.005 for other in values)


def _matches(value: float, fact: Fact, kind: Kind, keys: set[str]) -> bool:
    if fact.kind != kind:
        return False

    if kind == "score":
        # Keyed: "runway subscore" may only match the runway subscore, and a
        # bare "resilience score" may only match the headline score. Without
        # this, any of the four scores validates a claim about any other.
        if keys and not (keys & _label_keys(fact.key)):
            return False
        if not keys and fact.key != "resilience.score":
            return False
        return abs(value - fact.value) < 0.5

    if kind == "money":
        target = fact.value
        tolerance = max(1.0, abs(target) * 0.005)
        if abs(value - target) <= tolerance:
            return True
        # The model may quote raw cents, or use a "k" suffix we already expanded.
        return abs(value - target * 100) <= max(1.0, abs(target) * 0.5)

    if kind == "months":
        if abs(value - fact.value) <= 0.05:
            return True
        # Prose rounds: "about 2 months", "nearly 3 months".
        import math

        return value in {
            float(math.floor(fact.value)),
            float(math.ceil(fact.value)),
            float(round(fact.value)),
        }

    if kind == "month_index":
        # Referring to any simulated month is fine ("in month 3 your cash dips"),
        # but a claim *about the breaking point* must match the actual breaking
        # point — otherwise inventing one the engine never found reads as
        # grounded just because the month is in range.
        if "breaking" in keys and fact.key != "breakingPoint.monthIndex":
            return False
        # The data is 0-based; the prompt permits 1-based prose.
        return value in {fact.value, fact.value + 1}

    return abs(value - fact.value) < 0.005


_LABEL_KEYWORDS: dict[str, set[str]] = {
    "resilience.runwaySubscore": {"runway"},
    "resilience.bufferSubscore": {"buffer"},
    "resilience.creditSubscore": {"credit"},
    "resilience.score": {"resilience", "overall"},
}


def _label_keys(label: str) -> set[str]:
    return _LABEL_KEYWORDS.get(label, set())


def _money(cents: int | None, label: str) -> list[Fact]:
    if cents is None:
        return []
    return [Fact(value=cents / 100, kind="money", label=label)]


def facts_from_result(result: SimulateResponse, prefix: str = "") -> list[Fact]:
    """Every number a reply may quote from one simulation run."""
    facts: list[Fact] = []
    p = f"{prefix}." if prefix else ""

    baseline = result.baseline
    for name in (
        "fixedExpensesCents",
        "essentialExpensesCents",
        "totalExpensesCents",
        "monthlyBufferCents",
    ):
        facts += _money(getattr(baseline, name), f"{p}baseline.{name}")

    if baseline.runwayMonths is not None:
        facts.append(
            Fact(baseline.runwayMonths, "months", f"{p}baseline.runwayMonths")
        )

    resilience = result.resilience
    for name in ("score", "runwaySubscore", "bufferSubscore", "creditSubscore"):
        facts.append(
            Fact(float(getattr(resilience, name)), "score", f"{p}resilience.{name}")
        )

    breaking = result.breakingPoint
    if breaking.triggered and breaking.monthIndex is not None:
        facts.append(
            Fact(float(breaking.monthIndex), "month_index", f"{p}breakingPoint.monthIndex")
        )
    facts += _money(breaking.overageCents, f"{p}breakingPoint.overageCents")

    plan = result.preventionPlan
    if plan is not None:
        facts += _money(plan.extraSavingsCentsNeeded, f"{p}preventionPlan.extraSavings")
        facts += _money(plan.monthlyCutCentsNeeded, f"{p}preventionPlan.monthlyCut")
        facts += _money(plan.cuttableMonthlyCents, f"{p}preventionPlan.cuttable")

    for month in result.simulation.months:
        facts += _money(month.state.cashCents, f"{p}month{month.monthIndex}.cash")
        facts += _money(
            month.state.creditCardBalanceCents, f"{p}month{month.monthIndex}.credit"
        )
        # The simulation genuinely covers these months, so pointing at one is
        # grounded. What happens *at* it is checked separately, above.
        facts.append(
            Fact(float(month.monthIndex), "month_index", f"{p}simulation.monthIndex")
        )

    facts.append(
        Fact(float(len(result.simulation.months)), "count", f"{p}simulation.horizon")
    )
    facts.append(
        Fact(float(len(result.simulation.months)), "months", f"{p}simulation.horizon")
    )

    return facts


_NUMBER_IN_TEXT = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def numbers_in(text: str) -> set[float]:
    """Every numeric token in a blob of text, for the echo set."""
    found: set[float] = set()
    for match in _NUMBER_IN_TEXT.finditer(text or ""):
        try:
            found.add(float(match.group(0).replace(",", "")))
        except ValueError:
            continue
    return found


def _echoed_from_arguments(arguments: object) -> set[float]:
    """Numeric leaves of a tool-call argument dict, plus dollar equivalents."""
    echoed: set[float] = set()

    def walk(node: object, key: str = "") -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, list):
            for item in node:
                walk(item, key)
        elif isinstance(node, bool):
            return
        elif isinstance(node, (int, float)):
            echoed.add(float(node))
            if key.endswith("Cents"):
                echoed.add(float(node) / 100)

    walk(arguments)
    return echoed


def facts_from_lookup(result: dict, prefix: str = "") -> list[Fact]:
    """Every number a reply may quote from one web-backed cost estimate.

    These are a weaker class of fact than a simulation result: Python did the
    multiplication, but the price underneath came off a third-party page and
    could be stale or wrong. They are admitted anyway, because the alternative is
    worse — the guardrail would withhold the very reply that shows the user the
    estimate, which is the whole interaction. What protects the budget is not the
    ledger but the confirmation step: nothing reaches the profile until the user
    says yes.
    """
    if not result.get("ok"):
        return []

    facts = _money(result.get("monthlyCostCents"), f"{prefix}.commute.monthlyCost")

    price = result.get("fuelPrice") or {}
    facts += _money(price.get("amountCents"), f"{prefix}.commute.fuelPrice")

    # The assumptions are quotable too: a reply saying "assuming 24.4 mpg" is
    # being transparent, and should not be punished for it.
    assumptions = result.get("assumptions") or {}
    for key in ("milesEachWay", "daysPerWeek", "milesPerGallon", "monthlyMiles"):
        value = assumptions.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            facts.append(
                Fact(value=float(value), kind="number", label=f"{prefix}.commute.{key}")
            )

    return facts


def build_ledger(
    simulate_results: Iterable[SimulateResponse] = (),
    tool_arguments: Iterable[dict] = (),
    user_messages: Iterable[str] = (),
    lookup_results: Iterable[dict] = (),
) -> Ledger:
    """Assemble everything the reply is allowed to say.

    An empty `simulate_results` yields an empty fact list — which is exactly
    what makes an ungrounded reply detectable rather than invisible.
    """
    facts: list[Fact] = []
    for index, result in enumerate(simulate_results):
        facts.extend(facts_from_result(result, prefix=f"run{index}"))
    for index, result in enumerate(lookup_results):
        facts.extend(facts_from_lookup(result, prefix=f"lookup{index}"))

    echoed: set[float] = set()
    for arguments in tool_arguments:
        echoed |= _echoed_from_arguments(arguments)
    for message in user_messages:
        echoed |= numbers_in(message)

    return Ledger(facts=facts, echoed=echoed)


# --------------------------------------------------------------------------
# Reading numbers out of a reply
# --------------------------------------------------------------------------

# Nouns that make a sentence financial enough to police its bare integers.
_LEDGER_NOUN = re.compile(
    r"\b(scor\w*|runway|buffer|breaking\s+point|month\w*|balance|credit|savings?|"
    r"cash|cut|overage|shortfall|deficit|expenses?|income|rent|afford\w*)\b",
    re.IGNORECASE,
)
_SECOND_PERSON = re.compile(r"\b(you|your|you're|yours)\b", re.IGNORECASE)
# Markers that a sentence is about the world in general, not about this user.
_GENERIC = re.compile(
    r"\b(typically|usually|generally|on\s+average|rule\s+of\s+thumb|is\s+considered|"
    r"are\s+considered|most\s+people|commonly|experts?|in\s+general|often|"
    r"or\s+(?:above|higher|more|better))\b",
    re.IGNORECASE,
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

_TOKEN = re.compile(
    r"""
    (?P<dollar>\$)?
    (?P<value>\d[\d,]*(?:\.\d+)?)
    (?P<suffix>
        \s*(?:k\b|thousand\b)
      | \s*%
      | \s*percent\b
      | \s*(?:x\b|times\b)
      | \s*months?\b
      | \s*(?:dollars?|bucks)\b
      | \s*/\s*100\b
      | \s*out\s+of\s+100\b
      | (?:st|nd|rd|th)\b
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SCORE_VERB = re.compile(r"\bscor(?:e|ed|es|ing)\b", re.IGNORECASE)


@dataclass(frozen=True)
class NumberToken:
    raw: str
    value: float
    token_class: TokenClass
    sentence: str
    context: str

    @property
    def is_checked(self) -> bool:
        # A sentence about the world in general is not a claim about this user,
        # whatever shape its numbers take. This is what lets "a score of 80 or
        # above is considered resilient" and "payday loans typically carry 400%
        # APR" through untouched.
        if _is_generic_statement(self.sentence):
            return False
        if self.token_class in ALWAYS_CHECKED:
            return True
        if self.token_class != "bare":
            return False
        return _is_financial_context(self.sentence)

    @property
    def kind(self) -> Kind | None:
        return {
            "money": "money",
            "months": "months",
            "month_index": "month_index",
            "score_shaped": "score",
        }.get(self.token_class)

    @property
    def match_keys(self) -> set[str]:
        """Words near the number that narrow which fact may support it."""
        if self.token_class == "score_shaped":
            return self.score_keys
        if self.token_class == "month_index":
            breaking = re.search(
                r"\b(breaking\s+point|breaks?|break\s+down|fails?|goes\s+under)\b",
                self.context,
                re.IGNORECASE,
            )
            return {"breaking"} if breaking else set()
        return set()

    @property
    def score_keys(self) -> set[str]:
        found = {
            keyword
            for keyword in ("runway", "buffer", "credit", "resilience", "overall")
            if re.search(rf"\b{keyword}\b", self.context, re.IGNORECASE)
        }
        # "runway subscore" keys on runway; a bare "resilience score" keys on
        # nothing, which _matches() reads as "the headline score only".
        if "subscore" not in self.context.lower() and found <= {"resilience", "overall"}:
            return set()
        return found


def _is_generic_statement(sentence: str) -> bool:
    """A statement about the world rather than about this user."""
    return bool(_GENERIC.search(sentence)) and not _SECOND_PERSON.search(sentence)


def _is_financial_context(sentence: str) -> bool:
    return bool(_LEDGER_NOUN.search(sentence) and _SECOND_PERSON.search(sentence))


def _is_list_marker(match: re.Match[str], sentence: str, before: str) -> bool:
    """A markdown list number ("1. First lever"), not a claim.

    Deliberately narrow: the number must open the line AND be followed by a
    list punctuation mark. A sentence that merely starts with a figure —
    "3 months of runway is thin" — is a claim and stays checked.
    """
    if before.strip():
        return False
    return bool(re.match(r"[.)]\s", sentence[match.end() : match.end() + 2]))


# Account types whose *name* is a number: 401(k), 403(b), 457, 529. The digits
# are part of a product name, not a claim about this user's money — and the
# system prompt asks the agent to explain why raiding one is expensive, so this
# fires on exactly the replies the product wants.
_PLAN_NAME = re.compile(r"^\s*(?:\(\s*[kb]\s*\)|[kb]\b)", re.IGNORECASE)
_PLAN_NUMBERS = frozenset({"401", "403", "457", "529"})


def _is_plan_name(match: re.Match[str], sentence: str) -> bool:
    raw_value = match.group("value")
    if raw_value not in _PLAN_NUMBERS:
        return False
    # 401(k) / 403(b) carry their suffix; 457 and 529 need the noun nearby.
    if _PLAN_NAME.match(sentence[match.end() :]):
        return True
    return bool(
        re.search(
            r"\b(?:plan|account|retirement|savings\s+plan)\b",
            sentence[match.end() : match.end() + 30],
            re.IGNORECASE,
        )
    )


def _classify(match: re.Match[str], sentence: str, before: str) -> TokenClass:
    suffix = (match.group("suffix") or "").strip().lower()
    dollar = bool(match.group("dollar"))
    raw_value = match.group("value")

    if not dollar and _is_plan_name(match, sentence):
        return "plan_name"
    if dollar or suffix in {"dollars", "dollar", "bucks"}:
        return "money"
    if suffix in {"k", "thousand"}:
        return "money" if dollar else "bare"
    if suffix.startswith("month"):
        return "months"
    if suffix in {"/100", "/ 100"} or suffix.replace(" ", "") == "/100":
        return "score_shaped"
    if suffix.replace(" ", "") == "outof100":
        return "score_shaped"
    if suffix in {"%", "percent"}:
        return "percent_owned" if _SECOND_PERSON.search(sentence) else "percent_generic"
    if suffix in {"x", "times"}:
        return "multiplier"
    if suffix in {"st", "nd", "rd", "th"}:
        return "ordinal"
    # "month 3" — the noun leads, so no suffix fires. This is a claim about
    # *which* month something happens, which must be checked against
    # breakingPoint.monthIndex rather than against a rounded runway.
    if re.search(r"\bmonths?\s*$", before, re.IGNORECASE):
        return "month_index"
    if _SCORE_VERB.search(before[-30:]):
        return "score_shaped"
    if re.fullmatch(r"(?:19|20)\d{2}", raw_value):
        return "year"
    if _is_list_marker(match, sentence, before):
        return "list_marker"
    return "bare"


def tokens_in(text: str) -> list[NumberToken]:
    """Every number in a reply, classified by its own surface form."""
    tokens: list[NumberToken] = []

    for sentence in _SENTENCE_SPLIT.split(text or ""):
        if not sentence.strip():
            continue
        for match in _TOKEN.finditer(sentence):
            try:
                value = float(match.group("value").replace(",", ""))
            except ValueError:
                continue

            before = sentence[: match.start()]
            token_class = _classify(match, sentence, before)

            suffix = (match.group("suffix") or "").strip().lower()
            if token_class == "money" and suffix in {"k", "thousand"}:
                value *= 1000

            start = max(0, match.start() - 40)
            tokens.append(
                NumberToken(
                    raw=match.group(0).strip(),
                    value=value,
                    token_class=token_class,
                    sentence=sentence,
                    context=sentence[start : match.end() + 40],
                )
            )

    return tokens


def unsupported_numbers(text: str, ledger: Ledger) -> list[str]:
    """Figures in `text` the ledger cannot account for.

    Returns human-readable descriptions, used both to tell the model what to
    fix and to explain the block to the user.
    """
    problems: list[str] = []

    for token in tokens_in(text):
        if not token.is_checked:
            continue

        kind = token.kind
        if kind is None:
            supported = ledger.supports_any_kind(token.value)
        else:
            supported = ledger.supports(token.value, kind, token.match_keys)

        if not supported:
            problems.append(token.raw)

    # Preserve order, drop duplicates.
    seen: set[str] = set()
    return [p for p in problems if not (p in seen or seen.add(p))]
