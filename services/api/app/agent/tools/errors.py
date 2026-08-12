"""Turning validation failures into something the model can read and act on.

`ValidationError.errors()` embeds the original exception object under `ctx`,
which is not JSON-serialisable — and every tool result gets JSON-encoded on its
way back to the model. This flattens each error to plain strings.
"""

from pydantic import ValidationError


def validation_detail(error: ValidationError) -> list[dict[str, str]]:
    """JSON-safe, model-readable summary of what was wrong with the arguments."""
    return [
        {
            "field": ".".join(str(part) for part in item["loc"]) or "(root)",
            "problem": item["msg"],
            "type": item["type"],
        }
        for item in error.errors(include_url=False)
    ]
