import uuid

import pytest
from climatoology.base.operator import ComputationScope


@pytest.fixture
def compute_resources():
    with ComputationScope(uuid.uuid4()) as resources:
        yield resources
