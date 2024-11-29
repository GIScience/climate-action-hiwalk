import uuid
import shapely

import pytest
import responses
from climatoology.base.computation import ComputationScope
from climatoology.base.baseoperator import AoiProperties

from walkability.input import ComputeInputWalkability
from walkability.operator_worker import Operator
from walkability.utils import filter_start_matcher


@pytest.fixture
def expected_compute_input() -> ComputeInputWalkability:
    # noinspection PyTypeChecker
    return ComputeInputWalkability()


@pytest.fixture
def default_aoi() -> shapely.MultiPolygon:
    return shapely.MultiPolygon(
        polygons=[
            [
                [
                    [12.3, 48.22],
                    [12.3, 48.34],
                    [12.48, 48.34],
                    [12.48, 48.22],
                    [12.3, 48.22],
                ]
            ]
        ]
    )


@pytest.fixture
def default_aoi_properties() -> AoiProperties:
    return AoiProperties(name='Heidelberg', id='heidelberg')


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
    return Operator()


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
