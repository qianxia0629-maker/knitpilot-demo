import json
from pathlib import Path

import pytest

from apps.api.service import engine_input
from packages.schemas.spec import KnittingSpec


@pytest.fixture
def spec():
    return KnittingSpec.model_validate_json((Path(__file__).parents[1] / "fixtures/basic_pullover.json").read_text())


@pytest.fixture
def inputs(spec):
    return engine_input(spec)
