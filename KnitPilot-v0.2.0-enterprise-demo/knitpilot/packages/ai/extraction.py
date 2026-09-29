"""AI output contracts only. Provider integration follows in a later phase."""

from __future__ import annotations

from typing import Any

from packages.schemas.spec import Evidence, KnittingSpec, Operation


EXTRACTION_POLICY = """Extract only observed facts from supplied files. Output a KnittingSpec JSON object.
Every atomic field must have value, unit, source, confidence (0..1), confirmed.
Use null for missing values; never guess dimensions, gauge, needles or shrinkage.
Set confirmed=false for all machine-extracted values. Never produce stitch/row calculations.
Source must identify file/page/region when possible. Do not invent a source."""

OPERATION_POLICY = """Translate a user's instruction into a list of Operation JSON objects.
Only /measurements/<known_field> paths are allowed. Use absolute cm values; for relative
changes use the confirmed current value supplied in context. Require reason and user.
Never calculate or edit stitches, rows, shrinkage, QC, or machine settings."""


def validate_extraction(data: dict[str, Any]) -> KnittingSpec:
    """Validate provider JSON and refuse falsely preconfirmed extracted fields."""
    spec = KnittingSpec.model_validate(data)
    def inspect(value: Any) -> None:
        if isinstance(value, Evidence):
            if value.confirmed:
                raise ValueError("AI extraction cannot mark fields confirmed")
        elif isinstance(value, dict):
            for child in value.values():
                inspect(child)
        elif hasattr(value, "model_dump"):
            for child in value.__dict__.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)
    inspect(spec)
    return spec


def validate_operations(data: list[dict[str, Any]]) -> list[Operation]:
    """Validate parsed natural-language operations before applying them."""
    return [Operation.model_validate(item) for item in data]
