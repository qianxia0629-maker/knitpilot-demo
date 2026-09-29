"""Boundary adapter: confirmed evidence to scalar engine inputs."""

from __future__ import annotations

from dataclasses import fields
from datetime import datetime, timezone

from packages.engine import EngineInput
from packages.schemas.spec import Evidence, KnittingSpec, ManualEdit, Operation


def _required(evidence: Evidence | None, path: str, unit: str | None = None):
    if evidence is None or evidence.value is None or not evidence.confirmed:
        raise ValueError(f"{path} needs a confirmed value")
    if evidence.confidence < 0 or evidence.confidence > 1:
        raise ValueError(f"{path} confidence outside 0..1")
    if unit is not None and evidence.unit != unit:
        raise ValueError(f"{path} must use {unit}")
    return evidence.value


def engine_input(spec: KnittingSpec) -> EngineInput:
    """Reject unconfirmed required evidence and map immutable numeric inputs."""
    sections = {
        "stitches_per_10cm": spec.gauge.stitches_per_10cm,
        "rows_per_10cm": spec.gauge.rows_per_10cm,
        "horizontal_shrinkage": spec.shrinkage.horizontal,
        "vertical_shrinkage": spec.shrinkage.vertical,
        "min_needles": spec.machine.min_needles,
        "max_needles": spec.machine.max_needles,
        "pattern_repeat": spec.repeats.pattern_repeat,
        "rib_repeat": spec.repeats.rib_repeat,
        "neck_rib_kind": spec.neck_rib.kind,
        "shoulder_style": spec.garment.shoulder_style,
        "seam_tolerance_cm": spec.qc.seam_tolerance_cm,
        "dimension_tolerance_cm": spec.qc.dimension_tolerance_cm,
    }
    for f in fields(EngineInput):
        if f.name not in sections:
            sections[f.name] = getattr(spec.measurements, f.name)
    # Supported garment type is schema-constrained, but must still be confirmed.
    for name in ("style", "sleeve_style", "stitch_structure"):
        _required(getattr(spec.garment, name), f"garment.{name}")
    units = {"stitches_per_10cm": "stitches/10cm", "rows_per_10cm": "rows/10cm",
             "horizontal_shrinkage": "fraction", "vertical_shrinkage": "fraction",
             "min_needles": "stitches", "max_needles": "stitches",
             "pattern_repeat": "stitches", "rib_repeat": "stitches",
             "seam_tolerance_cm": "cm", "dimension_tolerance_cm": "cm"}
    return EngineInput(**{k: _required(v, k, units.get(k, "cm") if k not in ("neck_rib_kind", "shoulder_style") else None)
                         for k, v in sections.items()})


def apply_operations(spec: KnittingSpec, operations: list[Operation]) -> tuple[KnittingSpec, list[ManualEdit]]:
    """Copy spec, apply whitelisted edits in order; record audit, never mutate input."""
    updated = spec.model_copy(deep=True)
    edits = []
    for operation in operations:
        key = operation.path.split("/")[-1]
        old = getattr(updated.measurements, key)
        if old.value is None or not old.confirmed:
            raise ValueError(f"{operation.path} must first be confirmed")
        new = old.model_copy(update={"value": operation.value, "unit": "cm",
                                     "source": f"manual:{operation.user}", "confidence": 1.0, "confirmed": True})
        setattr(updated.measurements, key, new)
        edits.append(ManualEdit(field_path=operation.path, old_value=old.value,
                                new_value=operation.value, reason=operation.reason,
                                user=operation.user, timestamp=datetime.now(timezone.utc)))
    return updated, edits
