import pytest

from packages.engine import (
    calculate_armhole, calculate_body, calculate_neck, calculate_shoulder,
    calculate_sleeve, calculate_sleeve_cap, compensate_horizontal_shrinkage,
    compensate_vertical_shrinkage, distribute_decreases, distribute_increases,
    find_valid_stitch_count, fit_pattern_repeat, height_to_rows,
    validate_front_back_shoulders, validate_sleeve_armhole,
    validate_stitch_balance, validate_symmetry, width_to_stitches,
)
from packages.engine.core import Sequence


def test_shrinkage_inverse_and_rounding():
    assert compensate_horizontal_shrinkage(58, -.05) == pytest.approx(58 / .95)
    assert compensate_vertical_shrinkage(58, -.05) == pytest.approx(58 / .95)
    assert width_to_stitches(10.25, 20) == 21
    assert height_to_rows(10.5, 30) == 32


@pytest.mark.parametrize('func,args', [
    (width_to_stitches, (0, 20)), (width_to_stitches, (10, 0)),
    (height_to_rows, (-1, 30)), (height_to_rows, (10, -2)),
    (compensate_horizontal_shrinkage, (0, -.1)),
    (compensate_horizontal_shrinkage, (10, -1)),
    (compensate_vertical_shrinkage, (10, 1)),
])
def test_bad_dimensions(func, args):
    with pytest.raises(ValueError):
        func(*args)


def test_legalization_intersection_tie_and_error():
    result = find_valid_stitch_count(61, stitches_per_10cm=20,
                                     horizontal_shrinkage=-.05, even=True,
                                     symmetry=True, pattern_repeat=4,
                                     rib_repeat=6, machine_limit=(30, 100))
    assert result.selected_stitches == 60
    assert result.difference == -1
    assert result.width_error_cm == pytest.approx(-.475)
    assert 'multiple=12' in result.reason
    assert fit_pattern_repeat(13, 4, machine_limit=(4, 100)) == 12
    assert find_valid_stitch_count(11, stitches_per_10cm=20, even=True).selected_stitches == 10


@pytest.mark.parametrize('kwargs', [
    {'theoretical_stitches': 0}, {'theoretical_stitches': 10, 'stitches_per_10cm': 0},
    {'theoretical_stitches': 10, 'pattern_repeat': 0},
    {'theoretical_stitches': 10, 'rib_repeat': 0},
    {'theoretical_stitches': 10, 'machine_limit': (0, 1)},
    {'theoretical_stitches': 10, 'machine_limit': (30, 2)},
    {'theoretical_stitches': 10, 'machine_limit': (3, 3), 'pattern_repeat': 4},
    {'theoretical_stitches': 10, 'horizontal_shrinkage': -1},
    ])
def test_legalization_invalid(kwargs):
    with pytest.raises(ValueError):
        find_valid_stitch_count(**{'stitches_per_10cm': 20, **kwargs})


def test_compact_distribution():
    sequence = distribute_increases(92, 12)
    assert [s.notation() for s in sequence] == ['8-1-8', '7-1-4']
    assert sum(s.interval_rows * s.times for s in sequence) == 92
    assert sum(s.stitches * s.times for s in sequence) == 12
    assert distribute_decreases(12, 3, 2) == (Sequence(4, 2, 3),)
    assert distribute_increases(0, 0) == ()


@pytest.mark.parametrize('args', [(-1, 2, 1), (2, -1, 1), (2, 1, 0), (3, 4, 1), (2, 0, 1)])
def test_distribution_invalid(args):
    with pytest.raises(ValueError):
        distribute_decreases(*args)


def test_panel_conservation():
    arm = calculate_armhole(120, 100, 20)
    assert arm.end_stitches == 100
    assert arm.bind_off_each_side == 2
    assert calculate_armhole(100, 100, 20).decreases_each_side == ()
    neck = calculate_neck(100, 30, 10)
    assert neck.center_bind_off + 2 * sum(s.times * s.stitches for s in neck.decreases_each_side) == 30
    shoulder = calculate_shoulder(neck.shoulder_stitches_each_side, 4)
    assert shoulder.end_each_side == 0
    panel = calculate_body(120, 100, 100, 20, 10, 30, 10, 4)
    assert panel.final_stitches == 0
    assert panel.armhole_start_row == 80


@pytest.mark.parametrize('fn,args', [
    (calculate_armhole, (100, 101, 10)), (calculate_armhole, (101, 100, 10)),
    (calculate_armhole, (40, 2, 2)), (calculate_armhole, (40, 20, 0)),
    (calculate_neck, (50, 50, 5)), (calculate_neck, (51, 20, 5)),
    (calculate_neck, (50, 21, 5)), (calculate_neck, (50, 20, 0)),
    (calculate_shoulder, (0, 1)), (calculate_shoulder, (3, 4)),
    (calculate_body, (120, 100, 100, 20, 80, 30, 10, 4)),
    (calculate_body, (120, 100, 100, 20, 10, 30, 21, 4)),
    (calculate_body, (120, 100, 100, 20, 10, 30, 5, 6)),
    (calculate_sleeve_cap, (80, 1, 20)), (calculate_sleeve_cap, (80, 20, 21)),
    (calculate_sleeve_cap, (100, 2, 2)),
    (calculate_sleeve, (41, 80, 100, 20, 20)),
    (calculate_sleeve, (40, 80, 20, 20, 20)),
])
def test_invalid_shaping(fn, args):
    with pytest.raises(ValueError):
        fn(*args)


def test_sleeve_and_qc():
    sleeve = calculate_sleeve(40, 80, 100, 40, 20)
    assert sleeve.upper_stitches == 80
    assert sleeve.cap.top_bind_off == 20
    assert sleeve.final_stitches == 0
    assert calculate_sleeve(40, 40, 100, 40, 20).increases_each_side == ()
    assert calculate_sleeve_cap(8, 4, 6).decreases_each_side == ()
    assert calculate_sleeve(40, 80, 100, 0, 80).cap.top_bind_off == 80
    with pytest.raises(ValueError):
        calculate_sleeve(40, 80, 100, 0, 40)
    assert validate_stitch_balance(40, 40, 40, 40, 0).ok
    assert not validate_stitch_balance(40, 0, 0, 41, 0).ok
    assert validate_symmetry((Sequence(4, 1, 2),), (Sequence(4, 1, 2),)).ok
    assert not validate_symmetry((Sequence(4, 1, 2),), ()).ok


def test_relational_checks():
    panel = calculate_body(120, 100, 100, 20, 10, 30, 10, 4)
    sleeve = calculate_sleeve(40, 80, 100, 40, 20)
    assert validate_front_back_shoulders(panel, panel).ok
    other = calculate_body(120, 100, 100, 20, 10, 32, 10, 4)
    assert not validate_front_back_shoulders(panel, other).ok
    assert validate_sleeve_armhole(sleeve, panel, panel, 20, 30, 100).ok
    assert not validate_sleeve_armhole(sleeve, panel, panel, 20, 30, 0).ok
    with pytest.raises(ValueError):
        validate_sleeve_armhole(sleeve, panel, panel, 0, 30, 2)
    with pytest.raises(ValueError):
        validate_sleeve_armhole(sleeve, panel, panel, 20, 30, 2, -1)
