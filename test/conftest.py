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
        name='Walkable',
        modality=ArtifactModality.MAP_LAYER_GEOJSON,
        file_path=Path(compute_resources.computation_dir / 'walkable.geojson'),
        summary='Categories of the pedestrian paths based on the share with other road users.',
        description='Explanation of the different categories (from good to bad):\n'
        '* Dedicated exclusive: dedicated footways without other traffic close by.\n'
        '* Dedicated separated: dedicated footways with other traffic close by. This means for example sidewalks or segregated bike and footways (VZ 241, in Germany).\n'
        '* Designated shared with bikes: Footways shared with bikes, typically either a common foot and bikeway (VZ 240, in Germany) or footways where bikes are allowed to ride on (zVZ 1022-10, in Germany).\n'
        '* Shared with motorized traffic low speed: Streets without a sidewalk, with low speed limits, such as living streets or service ways.\n'
        '* Shared with motorized traffic medium speed: Streets without a sidewalk, with medium speed limits up to 30 km/h.\n'
        '* Shared with motorized traffic high speed: Streets without a sidewalk, with higher speed limits up to 50 km/h.\n'
        '* Not Walkable: Paths where walking is forbidden (e.g. tunnels, private or military streets) or streets without a sidewalk and with speed limits higher than 50 km/h.\n'
        '* Unknown: Paths that could not be fit in any of the above categories because of missing information.\n\n'
        'The data source is OpenStreetMap.',
        attachments={
            AttachmentType.LEGEND: Legend(
                legend_data={
                    'designated': Color('#006837'),
                    'designated_shared_with_bikes': Color('#66bd63'),
                    'shared_with_motorized_traffic_low_speed_max_walking_pace': Color('#d9ef8b'),
                    'shared_with_motorized_traffic_medium_speed_max_30_kph': Color('#fee08b'),
                    'shared_with_motorized_traffic_high_speed_max_50_kph': Color('#f46d43'),
                    'not_walkable': Color('#a50026'),
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
        summary='Map of connectivity scores.',
        description='Each path is evaluated based on the reachability of other paths within the area of interest. '
        'Reachability or connectivity is defined as the share of locations that can be reached by foot in '
        'reference to an optimum where all locations are directly connected "as the crow flies".',
        attachments={
            AttachmentType.LEGEND: Legend(
                legend_data=ContinuousLegendData(
                    cmap_name='RdYlGn',
                    ticks={'Low Connectivity': 0, 'Medium Connectivity': 0.5, 'High Connectivity': 1},
                )
            )
        },
    )
    pavement_quality_artifact = _Artifact(
        name='Pavement Quality',
        modality=ArtifactModality.MAP_LAYER_GEOJSON,
        file_path=Path(compute_resources.computation_dir / 'pavement_quality.geojson'),
        summary='The layer displays the pavement quality for the accessible paths of the walkable layer.',
        description='Based on the values of the `smoothness`, `surface` and `tracktype` tags of OpenStreetMap (in order of importance). '
        'If there is no specification for the pavement of non-exlusive footways, the quality of accompanying roads is adopted if available and labelled as *potential*. '
        'Some surface types, such as gravel, are also labelled *potential* as they can exhibit a wide variation in their maintenance status (see table below).\n\n'
        'Full list of tag-value-ranking combinations:\n\n'
        '' + Path('./test/test_utils.test_pavement_quality_info_generator.approved.txt').read_text(encoding='utf-8'),
        attachments={
            AttachmentType.LEGEND: Legend(
                legend_data={
                    'excellent': Color('#006837'),
                    'potentially_excellent': Color('#0c7f43'),
                    'good': Color('#84ca66'),
                    'potentially_good': Color('#a5d86a'),
                    'mediocre': Color('#feffbe'),
                    'potentially_mediocre': Color('#fff0a6'),
                    'poor': Color('#e54e35'),
                    'potentially_poor': Color('#d62f27'),
                    'unknown': Color('#808080'),
                }
            )
        },
    )
    chart_artifact_bergheim = _Artifact(
        name='Bergheim',
        modality=ArtifactModality.CHART,
        primary=False,
        file_path=Path(compute_resources.computation_dir / 'aggregation_Bergheim.json'),
        summary='The distribution of paths categories for this administrative area. '
        'The total length of paths in this area is 0.12 km',
        description=None,
    )
    chart_artifact_suedstadt = _Artifact(
        name='Südstadt',
        modality=ArtifactModality.CHART,
        primary=False,
        file_path=Path(compute_resources.computation_dir / 'aggregation_Südstadt.json'),
        summary='The distribution of paths categories for this administrative area. '
        'The total length of paths in this area is 0.12 km',
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
        open('resources/test/ohsome_line_and_polygon_response.geojson', 'r') as line_and_polygon_file,
        open('resources/test/ohsome_route_response.geojson', 'r') as route_file,
    ):
        line_and_polygon_body = line_and_polygon_file.read()
        route_body = route_file.read()

    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=line_and_polygon_body,
        match=[filter_start_matcher('(geometry:line or geometry:polygon)')],
    )

    responses_mock.post(
        'https://api.ohsome.org/v1/elements/geometry',
        body=route_body,
        match=[filter_start_matcher('route in (foot,hiking,bicycle)')],
    )
    return responses_mock
