"""Pure specification calculation and comprehensive draft QC."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .core import (
    PanelResult, QCResult, SleeveResult, StitchChoice, _events, _rows,
    calculate_body, calculate_sleeve, compensate_horizontal_shrinkage,
    compensate_vertical_shrinkage, find_valid_stitch_count, height_to_rows,
    validate_front_back_shoulders, validate_sleeve_armhole,
    validate_stitch_balance, validate_symmetry, width_to_stitches,
)


@dataclass(frozen=True)
class EngineInput:
    """Fully confirmed scalar inputs; adapters must reject missing evidence."""
    stitches_per_10cm: float
    rows_per_10cm: float
    horizontal_shrinkage: float
    vertical_shrinkage: float
    min_needles: int
    max_needles: int
    pattern_repeat: int
    rib_repeat: int
    neck_rib_kind: str
    shoulder_style: str
    chest_width: float
    body_length: float
    armhole_depth: float
    shoulder_width: float
    shoulder_slope: float
    neck_width: float
    front_neck_depth: float
    back_neck_depth: float
    sleeve_length: float
    sleeve_cuff_width: float
    sleeve_upper_width: float
    sleeve_cap_height: float
    sleeve_cap_top_width: float
    hem_rib_height: float
    neck_rib_height: float
    neck_rib_circumference: float
    seam_tolerance_cm: float
    dimension_tolerance_cm: float


@dataclass(frozen=True)
class Draft:
    back_panel: PanelResult
    front_panel: PanelResult
    sleeve: SleeveResult
    neck_rib_stitches: int
    neck_rib_rows: int
    choices: tuple[tuple[str, StitchChoice], ...]
    qc: tuple[QCResult, ...]


def _width(cm: float, i: EngineInput, *, rib: bool = False) -> StitchChoice:
    prewash = compensate_horizontal_shrinkage(cm, i.horizontal_shrinkage)
    theoretical = width_to_stitches(prewash, i.stitches_per_10cm)
    choice = find_valid_stitch_count(
        theoretical, stitches_per_10cm=i.stitches_per_10cm,
        horizontal_shrinkage=i.horizontal_shrinkage, even=True,
        symmetry=True, pattern_repeat=1 if rib else i.pattern_repeat,
        rib_repeat=i.rib_repeat if rib else 1,
        machine_limit=(i.min_needles, i.max_needles),
    )
    # Report the actual washed target error, including integer stitch rounding.
    actual_cm = choice.selected_stitches * 10 / i.stitches_per_10cm * (1 + i.horizontal_shrinkage)
    return replace(choice, width_error_cm=actual_cm - cm)


def _height(cm: float, i: EngineInput) -> int:
    return height_to_rows(compensate_vertical_shrinkage(cm, i.vertical_shrinkage), i.rows_per_10cm)


def calculate_spec(i: EngineInput) -> Draft:
    """Create a draft from confirmed measurements without any model calls."""
    if i.neck_rib_kind not in ("1x1", "2x2") or i.rib_repeat != (2 if i.neck_rib_kind == "1x1" else 4):
        raise ValueError("rib repeat must agree with 1x1/2x2 rib type")
    if i.shoulder_style not in ("set_in", "drop"):
        raise ValueError("unsupported shoulder style")
    if not 0 < i.armhole_depth < i.body_length or not 0 <= i.sleeve_cap_height < i.sleeve_length:
        raise ValueError("invalid garment proportions")
    if i.shoulder_style == "set_in" and i.sleeve_cap_height <= 0:
        raise ValueError("set-in sleeve needs a positive cap height")
    if i.shoulder_style == "drop" and i.sleeve_cap_height != 0:
        raise ValueError("drop sleeve uses a flat cap height of zero")
    if min(i.front_neck_depth, i.back_neck_depth, i.shoulder_slope) <= 0 or i.front_neck_depth > i.armhole_depth or i.back_neck_depth > i.armhole_depth:
        raise ValueError("invalid neckline/shoulder depth")
    if i.neck_width >= i.shoulder_width or i.shoulder_width > i.chest_width or i.sleeve_cuff_width > i.sleeve_upper_width:
        raise ValueError("incompatible widths")
    names = (
        ("chest", i.chest_width, False), ("shoulder", i.shoulder_width, False),
        ("neck", i.neck_width, False), ("cuff", i.sleeve_cuff_width, True),
        ("sleeve_upper", i.sleeve_upper_width, False),
        ("sleeve_cap_top", i.sleeve_cap_top_width, False),
        ("neck_rib", i.neck_rib_circumference, True),
    )
    choices = tuple((name, _width(cm, i, rib=rib)) for name, cm, rib in names)
    s = {name: choice.selected_stitches for name, choice in choices}
    if i.shoulder_style == "drop" and (s["shoulder"] != s["chest"] or s["sleeve_cap_top"] != s["sleeve_upper"]):
        raise ValueError("drop shoulder must match chest and flat sleeve top must match upper sleeve")
    total = _height(i.body_length, i)
    armhole_rows = _height(i.armhole_depth, i)
    slope = _height(i.shoulder_slope, i)
    common = (s["chest"], s["shoulder"], total, armhole_rows,
              _height(i.hem_rib_height, i), s["neck"])
    front = calculate_body(*common, _height(i.front_neck_depth, i), slope)
    back = calculate_body(*common, _height(i.back_neck_depth, i), slope)
    sleeve = calculate_sleeve(s["cuff"], s["sleeve_upper"], _height(i.sleeve_length, i),
                              _height(i.sleeve_cap_height, i) if i.sleeve_cap_height else 0,
                              s["sleeve_cap_top"])
    draft = Draft(back, front, sleeve, s["neck_rib"], _height(i.neck_rib_height, i), choices, ())
    return Draft(back, front, sleeve, s["neck_rib"], draft.neck_rib_rows,
                 choices, validate_spec(i, draft))


def validate_spec(i: EngineInput, draft: Draft) -> tuple[QCResult, ...]:
    """Check arithmetic, dimensions, height layout, repeats, machine and seams."""
    checks: list[QCResult] = []
    for name, p in (("front", draft.front_panel), ("back", draft.back_panel)):
        a, n, sh = p.armhole, p.neck, p.shoulder
        arm_decreases = 2 * _events(a.decreases_each_side)
        arm_bind = 2 * a.bind_off_each_side
        neck_decreases = 2 * _events(n.decreases_each_side)
        shoulder_bind = 2 * _events(sh.bind_off_each_side)
        checks.append(_named(validate_stitch_balance(p.cast_on, 0, arm_decreases + neck_decreases,
                              arm_bind + n.center_bind_off + shoulder_bind, p.final_stitches), f"{name}_balance"))
        checks.append(_named(validate_symmetry(a.decreases_each_side, a.decreases_each_side), f"{name}_armhole_symmetry"))
        checks.append(_named(validate_symmetry(n.decreases_each_side, n.decreases_each_side), f"{name}_neck_symmetry"))
        checks.append(QCResult(f"{name}_total_height", p.total_rows == p.armhole_start_row + a.shaping_rows and
                               p.rib_rows < p.armhole_start_row and n.shaping_rows <= a.shaping_rows and
                               sh.slope_rows <= n.shaping_rows, "row layout"))
        checks.append(QCResult(f"{name}_neck_width", n.center_bind_off + 2 * _events(n.decreases_each_side) ==
                               dict(draft.choices)["neck"].selected_stitches, "neck opening stitches"))
    sl, c = draft.sleeve, draft.sleeve.cap
    checks.append(_named(validate_stitch_balance(sl.cast_on, 2 * _events(sl.increases_each_side),
                          2 * _events(c.decreases_each_side),
                          2 * c.base_bind_off_each_side + c.top_bind_off, sl.final_stitches), "sleeve_balance"))
    checks.append(_named(validate_symmetry(sl.increases_each_side, sl.increases_each_side), "sleeve_symmetry"))
    checks.append(QCResult("sleeve_rows", sl.rows_before_cap + c.cap_rows == _height(i.sleeve_length, i)
                           and _rows(sl.increases_each_side) in (0, sl.rows_before_cap)
                           and _rows(c.decreases_each_side) in (0, c.cap_rows), "sleeve row layout"))
    checks.append(QCResult("sleeve_upper_width", sl.upper_stitches == c.start_stitches, "upper sleeve/cap join"))
    checks.append(QCResult("sleeve_cap", c.top_bind_off == dict(draft.choices)["sleeve_cap_top"].selected_stitches,
                           "cap top bind-off"))
    checks.append(validate_front_back_shoulders(draft.front_panel, draft.back_panel))
    checks.append(validate_sleeve_armhole(sl, draft.front_panel, draft.back_panel,
                                          i.stitches_per_10cm, i.rows_per_10cm, i.seam_tolerance_cm,
                                          i.horizontal_shrinkage, i.vertical_shrinkage))
    for name, choice in draft.choices:
        repeat = i.rib_repeat if name in ("cuff", "neck_rib") else i.pattern_repeat
        checks.append(QCResult(f"{name}_machine", i.min_needles <= choice.selected_stitches <= i.max_needles,
                               f"{choice.selected_stitches} within needle range"))
        checks.append(QCResult(f"{name}_repeat", choice.selected_stitches % repeat == 0,
                               f"{choice.selected_stitches} % {repeat} = 0"))
        checks.append(QCResult(f"{name}_dimension", abs(choice.width_error_cm) <= i.dimension_tolerance_cm,
                               f"finished width quantization error {choice.width_error_cm:+.3f}cm"))
    checks.append(QCResult("rib_height", 0 < draft.neck_rib_rows and 0 < draft.front_panel.rib_rows,
                           "positive rib heights"))
    for name, actual_rows, target_cm in (
        ("body_length", draft.front_panel.total_rows, i.body_length),
        ("armhole_depth", draft.front_panel.armhole.shaping_rows, i.armhole_depth),
        ("front_neck_depth", draft.front_panel.neck.shaping_rows, i.front_neck_depth),
        ("back_neck_depth", draft.back_panel.neck.shaping_rows, i.back_neck_depth),
        ("shoulder_slope", draft.front_panel.shoulder.slope_rows, i.shoulder_slope),
        ("sleeve_length", sl.rows_before_cap + c.cap_rows, i.sleeve_length),
        ("sleeve_cap_height", c.cap_rows, i.sleeve_cap_height),
        ("hem_rib_height", draft.front_panel.rib_rows, i.hem_rib_height),
        ("neck_rib_height", draft.neck_rib_rows, i.neck_rib_height),
    ):
        error = actual_rows * 10 / i.rows_per_10cm * (1 + i.vertical_shrinkage) - target_cm
        checks.append(QCResult(f"{name}_dimension", abs(error) <= i.dimension_tolerance_cm,
                               f"finished height error {error:+.3f}cm"))
    return tuple(checks)


def _named(check: QCResult, code: str) -> QCResult:
    return QCResult(code, check.ok, check.detail)
