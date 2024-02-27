import uuid
from pathlib import Path
from typing import List

import pytest
import responses
from climatoology.base.artifact import ArtifactModality
from climatoology.base.computation import ComputationScope
from climatoology.base.operator import Concern, Info, PluginAuthor, _Artifact
from semver import Version

from walkability.input import ComputeInputWalkability
from walkability.operator_worker import OperatorWalkability


@pytest.fixture
def expected_compute_input() -> ComputeInputWalkability:
    # noinspection PyTypeChecker
    return ComputeInputWalkability(
        aoi_blueprint={
            'type': 'Feature',
            'properties': None,
            'geometry': {
                'type': 'MultiPolygon',
                'coordinates': [
                    [
                        [
                            [12.3, 48.22],
                            [12.3, 48.34],
                            [12.48, 48.34],
                            [12.48, 48.22],
                            [12.3, 48.22],
                        ]
                    ]
                ],
            },
        },
    )


@pytest.fixture
def expected_info_output() -> Info:
    # noinspection PyTypeChecker
    return Info(
        name='Walkability',
        icon=Path('resources/info/icon.jpeg'),
        authors=[
            PluginAuthor(
                name='Moritz Schott',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            )
        ],
        version=Version(0, 0, 1),
        concerns=[Concern.CLIMATE_ACTION__GHG_EMISSION],
        purpose=Path('resources/info/purpose.md').read_text(),
        methodology=Path('resources/info/methodology.md').read_text(),
        sources=Path('resources/info/sources.bib'),
    )


@pytest.fixture
def expected_compute_output(compute_resources) -> List[_Artifact]:
    sidewalks_artifact = _Artifact(
        name='Sidewalks',
        modality=ArtifactModality.MAP_LAYER_GEOJSON,
        file_path=Path(compute_resources.computation_dir / 'sidewalks.geojson'),
        summary='The layer highlights roads that have sidewalks or are explicitly dedicated to pedestrians.',
        description='The layer features all roads that are neither highways/motorways nor specifically exclude '
        'pedestrians, such as cycle ways.',
    )
    return [
        sidewalks_artifact,
    ]


# The following fixtures can be ignored on plugin setup
@pytest.fixture
def compute_resources():
    with ComputationScope(uuid.uuid4()) as resources:
        yield resources


@pytest.fixture
def ohsome_api():
    with responses.RequestsMock() as rsps, open('resources/test/ohsome.geojson', 'rb') as vector:
        rsps.post('https://api.ohsome.org/v1/elements/geometry', body=vector.read())
        yield rsps


@pytest.fixture
def operator():
    return OperatorWalkability()
