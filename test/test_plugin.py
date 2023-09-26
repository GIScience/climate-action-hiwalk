from pathlib import Path
from typing import List

import pytest
from climatoology.base.operator import Info, Artifact, Concern, ArtifactModality
from semver import Version

from plugin.plugin import BlueprintOperator, BlueprintComputeInput


@pytest.fixture
def expected_info_output() -> Info:
    return Info(name='BlueprintOperator',
                icon=Path('resources/icon.jpeg'),
                version=Version(0, 0, 1),
                concerns=[Concern.GHG_EMISSION],
                purpose='This Operator serves no purpose besides being a blueprint for real operators.',
                methodology='This Operator uses no methodology because it does nothing.')


@pytest.fixture
def expected_compute_input() -> BlueprintComputeInput:
    return BlueprintComputeInput(blueprint_attribute="blueprint")


@pytest.fixture
def expected_compute_output() -> List[Artifact]:
    first_artifact = Artifact(name="Blueprint",
                              modality=ArtifactModality.TEXT,
                              file_path=Path('resources/blueprint.txt'),
                              summary='The input parameter.',
                              description='Raw return of the input parameter')
    return [first_artifact]


def test_plugin_info_request(expected_info_output):
    operator = BlueprintOperator()
    assert operator.info() == expected_info_output


def test_plugin_compute_request(expected_compute_input, expected_compute_output):
    operator = BlueprintOperator()
    assert operator.compute(expected_compute_input) == expected_compute_output
