"""Versioned input contract; evidence accompanies every extracted atomic value."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

T = TypeVar("T")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Evidence(StrictModel, Generic[T]):
    value: T | None = None
    unit: str | None = None
    source: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    confirmed: bool = False

    @model_validator(mode="after")
    def missing_is_unconfirmed(self) -> "Evidence[T]":
        if self.value is None and self.confirmed:
            raise ValueError("missing values cannot be confirmed")
        return self


class Project(StrictModel):
    name: Evidence[str]
    size: Evidence[str]


class Garment(StrictModel):
    style: Evidence[Literal["crew_neck_pullover"]]
    sleeve_style: Evidence[Literal["long"]]
    shoulder_style: Evidence[Literal["set_in", "drop"]]
    stitch_structure: Evidence[Literal["stockinette"]]


class Machine(StrictModel):
    name: Evidence[str] | None = None
    min_needles: Evidence[int]
    max_needles: Evidence[int]


class Yarn(StrictModel):
    description: Evidence[str] | None = None


class Gauge(StrictModel):
    stitches_per_10cm: Evidence[float]
    rows_per_10cm: Evidence[float]


class Shrinkage(StrictModel):
    # Fractional dimensional change: -0.05 means 5% smaller after washing.
    horizontal: Evidence[float]
    vertical: Evidence[float]


class Measurements(StrictModel):
    # Washed finished measurements in cm; panel widths are flat widths.
    chest_width: Evidence[float]
    body_length: Evidence[float]
    armhole_depth: Evidence[float]
    shoulder_width: Evidence[float]
    shoulder_slope: Evidence[float]
    neck_width: Evidence[float]
    front_neck_depth: Evidence[float]
    back_neck_depth: Evidence[float]
    sleeve_length: Evidence[float]
    sleeve_cuff_width: Evidence[float]
    sleeve_upper_width: Evidence[float]
    sleeve_cap_height: Evidence[float]
    sleeve_cap_top_width: Evidence[float]
    hem_rib_height: Evidence[float]
    neck_rib_height: Evidence[float]
    neck_rib_circumference: Evidence[float]


class RepeatConstraints(StrictModel):
    pattern_repeat: Evidence[int]
    rib_repeat: Evidence[Literal[2, 4]]


class Panel(StrictModel):
    notes: Evidence[str] | None = None


class Sleeve(Panel):
    pass


class NeckRib(StrictModel):
    kind: Evidence[Literal["1x1", "2x2"]]


class QCConfig(StrictModel):
    # Washed seam length tolerances, in cm. They must be factory approved.
    seam_tolerance_cm: Evidence[float]
    dimension_tolerance_cm: Evidence[float]


class Source(StrictModel):
    file_ids: list[str] = Field(default_factory=list)
    extraction_model: str | None = None


class KnittingSpec(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    project: Project
    garment: Garment
    machine: Machine
    yarn: Yarn
    gauge: Gauge
    shrinkage: Shrinkage
    measurements: Measurements
    back_panel: Panel
    front_panel: Panel
    sleeve: Sleeve
    neck_rib: NeckRib
    qc: QCConfig
    source: Source
    repeats: RepeatConstraints


class Operation(StrictModel):
    op: Literal["replace"]
    path: str
    value: float
    reason: str
    user: str

    @field_validator("path")
    @classmethod
    def allowed_path(cls, path: str) -> str:
        if path not in {f"/measurements/{x}" for x in Measurements.model_fields}:
            raise ValueError("only known measurement paths can be changed")
        return path


class ManualEdit(StrictModel):
    field_path: str
    old_value: float | None
    new_value: float
    reason: str
    user: str
    timestamp: datetime


class SpecVersion(StrictModel):
    version_id: str
    parent_version_id: str | None
    state: Literal["ai_draft", "manual_revision", "qc_revision", "final"]
    spec: KnittingSpec
    manual_edits: list[ManualEdit] = Field(default_factory=list)
    created_at: datetime
