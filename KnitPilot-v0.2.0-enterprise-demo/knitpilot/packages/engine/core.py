"""Pure, deterministic arithmetic for V1 flat-knit draft specifications.

All sizes are washed finished centimeters. Gauge describes the unwashed fabric.
Sequences apply symmetrically to BOTH edges unless explicitly marked center.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from math import gcd, hypot
from typing import Iterable


def _round(value: float) -> int:
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _positive(value: float, label: str) -> None:
    if value <= 0:
        raise ValueError(f"{label} must be positive")


def width_to_stitches(width_cm: float, stitches_per_10cm: float) -> int:
    """Round a prewash width to a theoretical whole stitch count."""
    _positive(width_cm, "width_cm")
    _positive(stitches_per_10cm, "stitches_per_10cm")
    return _round(width_cm * stitches_per_10cm / 10)


def height_to_rows(height_cm: float, rows_per_10cm: float) -> int:
    """Round a prewash height to a theoretical whole row count."""
    _positive(height_cm, "height_cm")
    _positive(rows_per_10cm, "rows_per_10cm")
    return _round(height_cm * rows_per_10cm / 10)


def compensate_horizontal_shrinkage(target_cm: float, shrinkage: float) -> float:
    """Invert dimensional change; -0.05 implies target / 0.95."""
    _positive(target_cm, "target_cm")
    if not -1 < shrinkage < 1:
        raise ValueError("shrinkage must lie strictly between -1 and 1")
    return target_cm / (1 + shrinkage)


def compensate_vertical_shrinkage(target_cm: float, shrinkage: float) -> float:
    """Invert vertical dimensional change using the same exact formula."""
    return compensate_horizontal_shrinkage(target_cm, shrinkage)


@dataclass(frozen=True)
class StitchChoice:
    selected_stitches: int
    theoretical_stitches: int
    difference: int
    width_error_cm: float
    reason: str


def find_valid_stitch_count(
    theoretical_stitches: int, *, stitches_per_10cm: float,
    horizontal_shrinkage: float = 0, even: bool = False,
    symmetry: bool = False, pattern_repeat: int = 1,
    rib_repeat: int = 1, machine_limit: tuple[int, int] = (1, 9999),
) -> StitchChoice:
    """Find closest multiple of all repeats in an inclusive needle range.

    Equal-distance ties choose the smaller count; error is finished width error.
    """
    _positive(theoretical_stitches, "theoretical_stitches")
    _positive(stitches_per_10cm, "stitches_per_10cm")
    if pattern_repeat < 1 or rib_repeat < 1 or machine_limit[0] < 1 or machine_limit[1] < machine_limit[0]:
        raise ValueError("invalid repeats or machine limit")
    if not -1 < horizontal_shrinkage < 1:
        raise ValueError("invalid shrinkage")
    multiple = 2 if even or symmetry else 1
    multiple = multiple * pattern_repeat // gcd(multiple, pattern_repeat)
    multiple = multiple * rib_repeat // gcd(multiple, rib_repeat)
    lo, hi = machine_limit
    candidates = range(((lo + multiple - 1) // multiple) * multiple, hi + 1, multiple)
    chosen = min(candidates, key=lambda n: (abs(n - theoretical_stitches), n), default=None)
    if chosen is None:
        raise ValueError("no legal count within machine range")
    error = (chosen - theoretical_stitches) * 10 / stitches_per_10cm * (1 + horizontal_shrinkage)
    return StitchChoice(chosen, theoretical_stitches, chosen - theoretical_stitches, error,
                        f"multiple={multiple}; machine={lo}..{hi}; ties round down")


def fit_pattern_repeat(stitches: int, repeat: int, *, machine_limit: tuple[int, int] = (1, 9999)) -> int:
    """Return nearest count satisfying a pattern repeat and machine bounds."""
    return find_valid_stitch_count(stitches, stitches_per_10cm=10,
                                   pattern_repeat=repeat, machine_limit=machine_limit).selected_stitches


@dataclass(frozen=True)
class Sequence:
    interval_rows: int
    stitches: int
    times: int

    def notation(self) -> str:
        """Render the factory rows-stitches-times notation."""
        return f"{self.interval_rows}-{self.stitches}-{self.times}"


def _distribute(rows: int, count: int, stitches: int) -> tuple[Sequence, ...]:
    """Compress floor/ceil intervals into at most two groups, exact total rows."""
    if rows < 0 or count < 0 or stitches < 1 or (count and rows < count) or (rows and not count):
        raise ValueError("impossible row/event allocation")
    if not count:
        return ()
    small, big_count = divmod(rows, count)
    # Larger intervals first, deterministic tie policy; groups share the same
    # side-specific sequence on left and right, preserving mirror symmetry.
    result = []
    if big_count:
        result.append(Sequence(small + 1, stitches, big_count))
    if count - big_count:
        result.append(Sequence(small, stitches, count - big_count))
    return tuple(result)


def distribute_increases(rows: int, times: int, stitches: int = 1) -> tuple[Sequence, ...]:
    """Allocate per-edge increase events over exactly `rows` rows."""
    return _distribute(rows, times, stitches)


def distribute_decreases(rows: int, times: int, stitches: int = 1) -> tuple[Sequence, ...]:
    """Allocate per-edge decrease events over exactly `rows` rows."""
    return _distribute(rows, times, stitches)


def _events(sequences: Iterable[Sequence]) -> int:
    return sum(s.stitches * s.times for s in sequences)


def _rows(sequences: Iterable[Sequence]) -> int:
    return sum(s.interval_rows * s.times for s in sequences)


@dataclass(frozen=True)
class PanelResult:
    cast_on: int
    total_rows: int
    rib_rows: int
    armhole_start_row: int
    armhole: "ArmholeResult"
    neck: "NeckResult"
    shoulder: "ShoulderResult"
    final_stitches: int


@dataclass(frozen=True)
class ArmholeResult:
    start_stitches: int
    bind_off_each_side: int
    decreases_each_side: tuple[Sequence, ...]
    shaping_rows: int
    end_stitches: int


@dataclass(frozen=True)
class NeckResult:
    start_stitches: int
    center_bind_off: int
    decreases_each_side: tuple[Sequence, ...]
    shaping_rows: int
    shoulder_stitches_each_side: int


@dataclass(frozen=True)
class ShoulderResult:
    start_each_side: int
    bind_off_each_side: tuple[Sequence, ...]
    slope_rows: int
    end_each_side: int


@dataclass(frozen=True)
class SleeveResult:
    cast_on: int
    upper_stitches: int
    rows_before_cap: int
    increases_each_side: tuple[Sequence, ...]
    cap: "SleeveCapResult"
    final_stitches: int


@dataclass(frozen=True)
class SleeveCapResult:
    start_stitches: int
    base_bind_off_each_side: int
    decreases_each_side: tuple[Sequence, ...]
    cap_rows: int
    top_bind_off: int


def calculate_armhole(start_stitches: int, upper_stitches: int, rows: int) -> ArmholeResult:
    """Basic symmetric underarm bind-off then one-stitch decreases."""
    delta = start_stitches - upper_stitches
    if start_stitches < 1 or upper_stitches < 1 or delta < 0 or delta % 2 or rows < 1:
        raise ValueError("armhole requires a nonnegative even reduction and positive rows")
    per_side = delta // 2
    base = min(2, per_side)
    events = per_side - base
    if events > rows:
        raise ValueError("armhole depth cannot accommodate decreases")
    seq = distribute_decreases(rows, events) if events else ()
    return ArmholeResult(start_stitches, base, seq, rows, start_stitches - 2 * (base + _events(seq)))


def calculate_neck(start_stitches: int, neck_stitches: int, neck_rows: int) -> NeckResult:
    """Bind center and taper to target opening while retaining equal shoulders."""
    if start_stitches < 1 or neck_stitches < 1 or neck_stitches >= start_stitches or neck_rows < 1:
        raise ValueError("invalid neck dimensions")
    if start_stitches % 2 or neck_stitches % 2:
        raise ValueError("neck and panel counts must be even")
    per_side = min(3, max(0, (neck_stitches - 2) // 2), neck_rows)
    center = neck_stitches - 2 * per_side
    seq = distribute_decreases(neck_rows, per_side) if per_side else ()
    shoulder = (start_stitches - neck_stitches) // 2
    return NeckResult(start_stitches, center, seq, neck_rows, shoulder)


def calculate_shoulder(shoulder_stitches: int, slope_rows: int) -> ShoulderResult:
    """Split each shoulder's bound-off stitches across slope rows."""
    if shoulder_stitches < 1 or slope_rows < 1 or slope_rows > shoulder_stitches:
        raise ValueError("invalid shoulder slope")
    small, big_count = divmod(shoulder_stitches, slope_rows)
    seq = ((Sequence(1, small + 1, big_count),) if big_count else ()) + (
        (Sequence(1, small, slope_rows - big_count),) if slope_rows - big_count else ())
    return ShoulderResult(shoulder_stitches, seq, slope_rows, shoulder_stitches - _events(seq))


def calculate_body(cast_on: int, upper_stitches: int, total_rows: int,
                   armhole_rows: int, rib_rows: int, neck_stitches: int,
                   neck_rows: int, shoulder_slope_rows: int) -> PanelResult:
    """Make one body panel with conserved armhole, neck, and shoulder counts."""
    if min(total_rows, armhole_rows, rib_rows, neck_rows, shoulder_slope_rows) < 1 or rib_rows >= total_rows - armhole_rows:
        raise ValueError("invalid body row layout")
    if neck_rows > armhole_rows or shoulder_slope_rows > neck_rows:
        raise ValueError("neck/shoulder rows exceed available armhole depth")
    arm = calculate_armhole(cast_on, upper_stitches, armhole_rows)
    neck = calculate_neck(arm.end_stitches, neck_stitches, neck_rows)
    shoulder = calculate_shoulder(neck.shoulder_stitches_each_side, shoulder_slope_rows)
    return PanelResult(cast_on, total_rows, rib_rows, total_rows - armhole_rows,
                       arm, neck, shoulder, 2 * shoulder.end_each_side)


def calculate_sleeve_cap(upper_stitches: int, cap_rows: int, top_stitches: int) -> SleeveCapResult:
    """Use symmetric base bind-off and taper; top binds off the remainder."""
    if upper_stitches < 4 or cap_rows < 2 or top_stitches < 2 or top_stitches >= upper_stitches or (upper_stitches - top_stitches) % 2:
        raise ValueError("invalid sleeve cap")
    per_side = (upper_stitches - top_stitches) // 2
    base = min(2, per_side)
    events = per_side - base
    if events > cap_rows:
        raise ValueError("cap too short for decreases")
    seq = distribute_decreases(cap_rows, events) if events else ()
    return SleeveCapResult(upper_stitches, base, seq, cap_rows,
                           upper_stitches - 2 * (base + _events(seq)))


def calculate_sleeve(cuff_stitches: int, upper_stitches: int, total_rows: int,
                     cap_rows: int, top_stitches: int) -> SleeveResult:
    """Increase both sleeve edges; zero cap rows means a flat drop sleeve top."""
    delta = upper_stitches - cuff_stitches
    if cuff_stitches < 1 or delta < 0 or delta % 2 or total_rows <= cap_rows or cap_rows < 0:
        raise ValueError("invalid sleeve dimensions")
    body_rows = total_rows - cap_rows
    seq = distribute_increases(body_rows, delta // 2) if delta else ()
    if cap_rows == 0:
        if top_stitches != upper_stitches:
            raise ValueError("flat sleeve top must equal upper sleeve count")
        cap = SleeveCapResult(upper_stitches, 0, (), 0, upper_stitches)
    else:
        cap = calculate_sleeve_cap(cuff_stitches + 2 * _events(seq), cap_rows, top_stitches)
    return SleeveResult(cuff_stitches, upper_stitches, body_rows, seq, cap, 0)


@dataclass(frozen=True)
class QCResult:
    code: str
    ok: bool
    detail: str


def validate_stitch_balance(cast_on: int, increases: int, decreases: int,
                            bind_off: int, final_stitches: int) -> QCResult:
    """Conserve stitches including every increase, decrease and bind-off."""
    ok = min(cast_on, increases, decreases, bind_off, final_stitches) >= 0 and cast_on + increases - decreases - bind_off == final_stitches
    return QCResult("stitch_balance", ok, f"{cast_on}+{increases}-{decreases}-{bind_off}={final_stitches}")


def validate_symmetry(left: Iterable[Sequence], right: Iterable[Sequence]) -> QCResult:
    """Require identical interval/event series on both edges."""
    return QCResult("symmetry", tuple(left) == tuple(right), "left and right shaping sequences")


def validate_front_back_shoulders(front: PanelResult, back: PanelResult) -> QCResult:
    """Ensure front and back shoulder stitches and bind-off plans agree."""
    ok = front.neck.shoulder_stitches_each_side == back.neck.shoulder_stitches_each_side and front.shoulder == back.shoulder
    return QCResult("front_back_shoulders", ok, "front/back shoulder stitch and slope match")


def validate_sleeve_armhole(sleeve: SleeveResult, front: PanelResult,
                            back: PanelResult, stitches_per_10cm: float,
                            rows_per_10cm: float, tolerance_cm: float,
                            horizontal_shrinkage: float = 0,
                            vertical_shrinkage: float = 0) -> QCResult:
    """Compare approximate sewn cap edge to two panel armhole edges.

    Staircase approximation is a screening check, not a replacement for a
    factory's measured seam geometry or easing specification.
    """
    if min(stitches_per_10cm, rows_per_10cm) <= 0 or tolerance_cm < 0:
        raise ValueError("invalid seam gauge/tolerance")
    if not -1 < horizontal_shrinkage < 1 or not -1 < vertical_shrinkage < 1:
        raise ValueError("invalid shrinkage for seam comparison")
    sx = 10 / stitches_per_10cm * (1 + horizontal_shrinkage)
    sy = 10 / rows_per_10cm * (1 + vertical_shrinkage)
    def arm_length(panel: PanelResult) -> float:
        a = panel.armhole
        return a.bind_off_each_side * sx + hypot(a.shaping_rows * sy, _events(a.decreases_each_side) * sx)
    c = sleeve.cap
    cap_length = (c.top_bind_off * sx if c.cap_rows == 0 else
                  2 * (c.base_bind_off_each_side * sx + hypot(c.cap_rows * sy, _events(c.decreases_each_side) * sx)))
    arm_length_total = arm_length(front) + arm_length(back)
    return QCResult("sleeve_armhole", abs(cap_length - arm_length_total) <= tolerance_cm,
                    f"cap={cap_length:.2f}cm; armhole={arm_length_total:.2f}cm; tolerance={tolerance_cm:.2f}cm")
