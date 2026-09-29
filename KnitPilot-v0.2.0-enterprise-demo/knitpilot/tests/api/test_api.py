import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.main import app
from apps.api.service import apply_operations, engine_input
from packages.ai.extraction import validate_extraction, validate_operations
from packages.engine import calculate_spec
from packages.schemas.spec import Evidence, Operation

client = TestClient(app)


def test_schema_and_evidence(spec):
    assert spec.schema_version == '1.0'
    with pytest.raises(ValidationError):
        Evidence[float](value=None, unit='cm', source='photo:1', confidence=.8, confirmed=True)
    with pytest.raises(ValidationError):
        Evidence[float](value=2, unit='cm', source='photo:1', confidence=1.1, confirmed=False)
    with pytest.raises(ValidationError):
        type(spec).model_validate({**spec.model_dump(), 'bad': 1})


def test_ai_never_confirms(spec):
    data = spec.model_dump()
    with pytest.raises(ValueError):
        validate_extraction(data)
    data['measurements']['chest_width']['confirmed'] = False
    with pytest.raises(ValueError):
        engine_input(type(spec).model_validate(data))
    for obj in (data['project'], data['garment'], data['machine'], data['yarn'],
                data['gauge'], data['shrinkage'], data['measurements'], data['neck_rib'],
                data['qc'], data['repeats']):
        for value in obj.values():
            if isinstance(value, dict) and 'confirmed' in value:
                value['confirmed'] = False
    assert validate_extraction(data).measurements.chest_width.confirmed is False


def test_operation_validation_and_recalculation(spec):
    op = Operation(op='replace', path='/measurements/chest_width', value=60,
                   reason='QC requested', user='technologist')
    new, edits = apply_operations(spec, [op])
    assert spec.measurements.chest_width.value == 58
    assert new.measurements.chest_width.value == 60
    assert edits[0].old_value == 58
    assert edits[0].field_path == op.path
    assert calculate_spec(engine_input(new)).back_panel.cast_on > calculate_spec(engine_input(spec)).back_panel.cast_on
    assert validate_operations([op.model_dump()]) == [op]
    with pytest.raises(ValidationError):
        Operation(op='replace', path='/machine/max_needles', value=400, reason='x', user='u')
    with pytest.raises(ValidationError):
        Operation(op='replace', path='/measurements/chest_width/extra', value=60, reason='x', user='u')


def test_api_calculate_and_preview(spec):
    assert client.get('/').json()['docs'] == '/docs'
    assert client.get('/health').json() == {'status': 'ok'}
    base = client.post('/v1/calculate', json=spec.model_dump()).json()
    assert base['back_panel']['cast_on'] > 0
    result = client.post('/v1/operations/preview', json={
        'spec': spec.model_dump(), 'operations': [{
            'op': 'replace', 'path': '/measurements/chest_width', 'value': 60,
            'reason': 'QC requested', 'user': 'technologist'}]})
    assert result.status_code == 200
    assert result.json()['draft']['back_panel']['cast_on'] > base['back_panel']['cast_on']
    assert result.json()['manual_edits'][0]['old_value'] == 58
    assert result.json()['spec']['measurements']['chest_width']['source'] == 'manual:technologist'


def test_api_rejects_missing_and_impossible(spec):
    data = spec.model_dump()
    data['gauge']['rows_per_10cm']['confirmed'] = False
    assert client.post('/v1/calculate', json=data).status_code == 422
    data = spec.model_dump()
    data['measurements']['front_neck_depth']['value'] = 100
    assert client.post('/v1/calculate', json=data).status_code == 422
    data = spec.model_dump()
    data['measurements']['chest_width']['confirmed'] = False
    body = {'spec': data, 'operations': [{'op': 'replace', 'path': '/measurements/chest_width',
            'value': 60, 'reason': 'test', 'user': 'qa'}]}
    assert client.post('/v1/operations/preview', json=body).status_code == 422
    data = spec.model_dump()
    data['measurements']['chest_width']['unit'] = 'mm'
    assert client.post('/v1/calculate', json=data).status_code == 422


def test_demo_access_code_is_required_when_configured(monkeypatch, spec):
    monkeypatch.setenv('KNITPILOT_DEMO_TOKEN', 'pilot-secret')
    body = spec.model_dump()
    assert client.post('/v1/calculate', json=body).status_code == 401
    assert client.post('/v1/calculate', json=body, headers={'X-Demo-Token': 'wrong'}).status_code == 401
    assert client.post('/v1/calculate', json=body, headers={'X-Demo-Token': 'pilot-secret'}).status_code == 200
    monkeypatch.setenv('KNITPILOT_REQUIRE_DEMO_TOKEN', '1')
    monkeypatch.delenv('KNITPILOT_DEMO_TOKEN')
    assert client.post('/v1/calculate', json=body).status_code == 503
