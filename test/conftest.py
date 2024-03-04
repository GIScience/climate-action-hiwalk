import uuid
from pathlib import Path
from typing import List, Any, Callable, Tuple
from urllib.parse import parse_qsl

import pytest
import responses
from climatoology.base.artifact import ArtifactModality
from climatoology.base.computation import ComputationScope
from climatoology.base.operator import Concern, Info, PluginAuthor, _Artifact
from requests import PreparedRequest
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
            )
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
        summary='The layer displays paths in four categories: '
        'a) paths dedicated to pedestrians exclusively '
        'b) paths that are explicitly meant for pedestrians but may be shared with other traffic (e.g. a '
        'road with a sidewalk) '
        'c) paths that probably are walkable but the true status is unknown (e.g. a dirt road) '
        'd) paths that are not walkable but could be (e.g. a residential road without sidewalk).',
        description='The layer excludes paths that are not walkable by definition such as motorways or cycle ways. '
        'The data source is OpenStreetMap.',
    )
    return [
        paths_artifact,
    ]


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
        open('resources/test/ohsome_line_response.geojson', 'rb') as line_file,
        open('resources/test/ohsome_polygon_response.geojson', 'rb') as polygon_file,
        open('resources/test/ohsome_route_response.geojson', 'rb') as route_file,
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


def filter_start_matcher(filter_start: str) -> Callable[..., Any]:
    def match(request: PreparedRequest) -> Tuple[bool, str]:
        request_body = request.body
        qsl_body = dict(parse_qsl(request_body, keep_blank_values=False)) if request_body else {}

        if request_body is None:
            return False, 'The given request has no body'
        elif qsl_body.get('filter') is None:
            return False, 'Filter parameter not set'
        else:
            valid = qsl_body.get('filter', '').startswith(filter_start)
            return (True, '') if valid else (False, f'The filter parameter does not start with {filter_start}')

    return match
