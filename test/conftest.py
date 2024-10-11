import uuid
from pathlib import Path
from typing import List

import pytest
import responses
from climatoology.base.artifact import ArtifactModality, AttachmentType, Legend, ContinuousLegendData
from climatoology.base.computation import ComputationScope
from climatoology.base.operator import Concern, Info, PluginAuthor, _Artifact
from pydantic_extra_types.color import Color
from semver import Version

from walkability.input import ComputeInputWalkability
from walkability.operator_worker import OperatorWalkability
from walkability.utils import filter_start_matcher


@pytest.fixture
def expected_compute_input() -> ComputeInputWalkability:
    # noinspection PyTypeChecker
    return ComputeInputWalkability(
        aoi={
            'type': 'Feature',
            'properties': {'name': 'Heidelberg', 'id': 'Q12345'},
            'geometry': {
                'type': 'MultiPolygon',
                'coordinates': [
                    [
                        [
                            [12.300, 48.220],
                            [12.300, 48.221],
                            [12.301, 48.221],
                            [12.301, 48.220],
                            [12.300, 48.220],
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
            ),
            PluginAuthor(
                name='Matthias Schaub',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Levi Szamek',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
            PluginAuthor(
                name='Jonas Kemmer',
                affiliation='HeiGIT gGmbH',
                website='https://heigit.org/heigit-team/',
            ),
        ],
        version=Version(0, 0, 1),
        concerns=[Concern.MOBILITY_PEDESTRIAN],
        purpose=Path('resources/info/purpose.md').read_text(),
        methodology=Path('resources/info/methodology.md').read_text(),
        sources=Path('resources/info/sources.bib'),
    )


@pytest.fixture
def expected_compute_output(compute_resources) -> List[_Artifact]:
    paths_artifact = _Artifact(
        name='Walkable Path Categories',
        modality=ArtifactModality.MAP_LAYER_GEOJSON,
        file_path=Path(compute_resources.computation_dir / 'walkable.geojson'),
        summary=Path('resources/info/path_categories/caption.md').read_text(),
        description=Path('resources/info/path_categories/description.md').read_text(),
        attachments={
            AttachmentType.LEGEND: Legend(
                legend_data={
                    'designated': Color('#313695'),
                    'designated_shared_with_bikes': Color('#6399c7'),
                    'shared_with_motorized_traffic_low_speed_(=walking_speed)': Color('#bde2ee'),
                    'shared_with_motorized_traffic_medium_speed_(<=30_km/h)': Color('#fffebe'),
                    'shared_with_motorized_traffic_high_speed_(<=50_km/h)': Color('#fdbf71'),
                    'not_walkable': Color('#ea5739'),
                    'unknown': Color('#808080'),
                }
            )
        },
    )
    connectivity = _Artifact(
        name='Connectivity',
        modality=ArtifactModality.MAP_LAYER_GEOJSON,
        primary=False,
        file_path=Path(compute_resources.computation_dir / 'connectivity.geojson'),
        summary=Path('resources/info/connectivity/caption.md').read_text(),
        description=Path('resources/info/connectivity/description.md').read_text(),
        attachments={
            AttachmentType.LEGEND: Legend(
                legend_data=ContinuousLegendData(
                    cmap_name='seismic',
                    ticks={'Low Connectivity': 1, 'Medium Connectivity': 0.5, 'High Connectivity': 0},
                )
            )
        },
    )
    pavement_quality_artifact = _Artifact(
        name='Surface Quality',
        modality=ArtifactModality.MAP_LAYER_GEOJSON,
        file_path=Path(compute_resources.computation_dir / 'pavement_quality.geojson'),
        summary=Path('resources/info/surface_quality/caption.md').read_text(),
        description=Path('resources/info/surface_quality/description.md').read_text()
        + Path('./test/test_utils.test_pavement_quality_info_generator.approved.txt').read_text(),
        attachments={
            AttachmentType.LEGEND: Legend(
                legend_data={
                    'excellent': Color('#313695'),
                    'potentially_excellent': Color('#5183bb'),
                    'good': Color('#90c3dd'),
                    'potentially_good': Color('#d4edf4'),
                    'mediocre': Color('#fffebe'),
                    'potentially_mediocre': Color('#fed283'),
                    'poor': Color('#f88c51'),
                    'potentially_poor': Color('#dd3d2d'),
                    'unknown': Color('#808080'),
                }
            )
        },
    )
    chart_artifact_bergheim = _Artifact(
        name='Distribution of Path Categories in Bergheim',
        modality=ArtifactModality.CHART,
        primary=False,
        file_path=Path(compute_resources.computation_dir / 'aggregation_Bergheim.json'),
        summary='Fraction of the total length of paths for each category compared to the total path length '
        'of 0.12 km in this area.',
        description=None,
    )
    chart_artifact_suedstadt = _Artifact(
        name='Distribution of Path Categories in Südstadt',
        modality=ArtifactModality.CHART,
        primary=False,
        file_path=Path(compute_resources.computation_dir / 'aggregation_Südstadt.json'),
        summary='Fraction of the total length of paths for each category compared to the total path length '
        'of 0.12 km in this area.',
        description=None,
    )

    return [paths_artifact, connectivity, pavement_quality_artifact, chart_artifact_bergheim, chart_artifact_suedstadt]


# The following fixtures can be ignored on plugin setup
@pytest.fixture
def compute_resources():
    with ComputationScope(uuid.uuid4()) as resources:
        yield resources


@pytest.fixture
def responses_mock():
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def operator():
    return OperatorWalkability()


@pytest.fixture
def ohsome_api(responses_mock):
    with (
        open('resources/test/ohsome_line_response.geojson', 'r') as line_file,
        open('resources/test/ohsome_polygon_response.geojson', 'r') as polygon_file,
        open('resources/test/ohsome_route_response.geojson', 'r') as route_file,
    ):
        line_body = line_file.read()
        polygon_body = polygon_file.read()
        route_body = route_file.read()

    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=line_body,
        match=[filter_start_matcher('geometry:line')],
    )

    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=polygon_body,
        match=[filter_start_matcher('geometry:polygon')],
    )

    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=route_body,
        match=[filter_start_matcher('route in (foot,hiking)')],
    )
    return responses_mock
