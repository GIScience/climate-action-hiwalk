from pathlib import Path
from typing import List

import pytest
from climatoology.base.operator import Info, Artifact, Concern, ArtifactModality
from semver import Version

from plugin.plugin import BlueprintOperator, BlueprintComputeInput


@pytest.fixture
def expected_info_output() -> Info:
    return Info(name='BlueprintPlugin',
                icon=Path('resources/icon.jpeg'),
                version=Version(0, 0, 1),
                concerns=[Concern.CLIMATE_ACTION__GHG_EMISSION],
                purpose='This Plugin serves no purpose besides being a blueprint for real plugins.',
                methodology='This Plugin uses no methodology because it does nothing.')


@pytest.fixture
def expected_compute_input() -> BlueprintComputeInput:
    return BlueprintComputeInput(blueprint_string="blueprint")


@pytest.fixture
def expected_compute_output(compute_resources) -> List[Artifact]:
    text_artifact = Artifact(name="Input Parameters",
                             modality=ArtifactModality.TEXT,
                             file_path=Path(compute_resources.computation_dir / 'blueprint.txt'),
                             summary='The input parameters.',
                             description='Raw return of the input parameter')
    raster_artifact = Artifact(name="LULC Classification",
                               modality=ArtifactModality.MAP_LAYER,
                               file_path=Path(compute_resources.computation_dir / 'raster.tiff'),
                               summary='The raw map data.',
                               description='A GeoTIFF.')
    return [text_artifact,
            raster_artifact]


def test_plugin_info_request(expected_info_output):
    operator = BlueprintOperator()
    assert operator.info() == expected_info_output


def test_plugin_compute_request(expected_compute_input, expected_compute_output, compute_resources, lulc_utility):
    operator = BlueprintOperator()
    assert operator.compute(resources=compute_resources,
                            params=expected_compute_input) == expected_compute_output
