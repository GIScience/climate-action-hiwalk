import uuid
from unittest.mock import patch

import geopandas as gpd
import pytest
import responses
import shapely
from climatoology.base.baseoperator import AoiProperties
from climatoology.base.computation import ComputationScope
from pyproj import CRS
from responses import matchers
from shapely.geometry import LineString

from test.components.utils.test_misc import filter_start_matcher
from walkability.core.input import ComputeInputWalkability
from walkability.core.operator_worker import OperatorWalkability


@pytest.fixture
def expected_compute_input() -> ComputeInputWalkability:
    return ComputeInputWalkability()


@pytest.fixture(scope='module')
def global_aoi() -> shapely.MultiPolygon:
    return shapely.MultiPolygon([[[[-90, -180], [90, -180], [90, 180], [-90, 180], [-90, -180]]]])


@pytest.fixture
def default_aoi() -> shapely.MultiPolygon:
    return shapely.MultiPolygon(
        polygons=[
            [
                [
                    [12.29, 48.20],
                    [12.29, 48.34],
                    [12.48, 48.34],
                    [12.48, 48.20],
                    [12.29, 48.20],
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


@pytest.fixture(scope='module')
def responses_mock():
    with responses.RequestsMock() as rsps:
        yield rsps


@pytest.fixture
def operator(naturalness_utility_mock):
    return OperatorWalkability(naturalness_utility_mock, ors_api_key='test-key')


@pytest.fixture
def ohsome_api(responses_mock):
    with (
        open('test/resources/ohsome_line_response.geojson', 'r') as line_file,
        open('test/resources/ohsome_polygon_response.geojson', 'r') as polygon_file,
        open('test/resources/ohsome_route_response.geojson', 'r') as route_file,
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


@pytest.fixture
def naturalness_utility_mock():
    with patch('climatoology.utility.Naturalness.NaturalnessUtility') as naturalness_utility:
        vectors = gpd.GeoSeries(
            index=[1, 2],
            data=[
                LineString([[12.4, 48.25], [12.4, 48.30]]),
                LineString([[12.41, 48.25], [12.41, 48.30]]),
            ],
            crs=CRS.from_epsg(4326),
        )
        return_gdf = gpd.GeoDataFrame(
            index=[1, 2], data={'median': [0.5, 0.6]}, geometry=vectors, crs=CRS.from_epsg(4326)
        )

        naturalness_utility.compute_vector.return_value = return_gdf
        yield naturalness_utility


@pytest.fixture
def ors_api(responses_mock):
    responses_mock.post(
        'https://api.openrouteservice.org/elevation/line',
        json={
            'attribution': 'service by https://openrouteservice.org | data by https://srtm.csi.cgiar.org',
            'geometry': [[12.3, 48.22, 1.0], [12.3005, 48.22, 2.0]],
            'timestamp': 1738238852,
            'version': '0.2.1',
        },
        match=[
            matchers.header_matcher({'Authorization': 'test-key'}),
            matchers.json_params_matcher(
                {
                    'format_in': 'polyline',
                    'format_out': 'polyline',
                    'dataset': 'srtm',
                    'geometry': [[12.3, 48.22], [12.3005, 48.22]],
                }
            ),
        ],
    )
    return responses_mock
