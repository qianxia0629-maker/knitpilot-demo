from dataclasses import replace

import pytest

from packages.engine import calculate_spec, validate_spec


def test_fixture_complete_and_deterministic(inputs):
    first, second = calculate_spec(inputs), calculate_spec(inputs)
    assert first == second
    assert first.front_panel.total_rows == first.back_panel.total_rows
    assert first.front_panel.neck.shaping_rows > first.back_panel.neck.shaping_rows
    assert first.sleeve.final_stitches == 0
    assert all(c.ok for c in first.qc), [(c.code, c.detail) for c in first.qc if not c.ok]
    assert validate_spec(inputs, first) == first.qc


@pytest.mark.parametrize('changes', [
    {'neck_rib_kind': '2x2'}, {'rib_repeat': 4}, {'shoulder_style': 'unknown'},
    {'armhole_depth': 64}, {'sleeve_cap_height': 60},
    {'front_neck_depth': 25}, {'shoulder_slope': 0},
    {'neck_width': 50}, {'shoulder_width': 59}, {'sleeve_cuff_width': 40},
    {'min_needles': 219, 'max_needles': 220},
    {'sleeve_cap_top_width': 38},
    {'shoulder_style': 'drop'},
    {'sleeve_cap_height': 0},
])
def test_impossible_spec_rejected(inputs, changes):
    with pytest.raises(ValueError):
        calculate_spec(replace(inputs, **changes))


def test_qc_reports_dimension_and_seam_failures(inputs):
    draft = calculate_spec(replace(inputs, dimension_tolerance_cm=0, seam_tolerance_cm=0))
    assert any(not c.ok and c.code.endswith('_dimension') for c in draft.qc)
    assert any(not c.ok and c.code == 'sleeve_armhole' for c in draft.qc)


def test_basic_drop_shoulder_uses_flat_sleeve_top(inputs):
    drop = replace(inputs, shoulder_style='drop', shoulder_width=inputs.chest_width,
                   sleeve_cap_height=0, sleeve_cap_top_width=inputs.sleeve_upper_width)
    draft = calculate_spec(drop)
    assert draft.back_panel.armhole.bind_off_each_side == 0
    assert draft.back_panel.armhole.decreases_each_side == ()
    assert draft.sleeve.cap.cap_rows == 0
    assert draft.sleeve.cap.top_bind_off == draft.sleeve.upper_stitches
    assert all(c.ok for c in draft.qc if c.code.endswith('_balance'))
