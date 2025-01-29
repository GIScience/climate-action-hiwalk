import uuid
from unittest.mock import patch

import geopandas as gpd
import pytest
import responses
import shapely
from climatoology.base.baseoperator import AoiProperties
from climatoology.base.computation import ComputationScope
from pyproj import CRS
from shapely.geometry.polygon import Polygon

from walkability.input import ComputeInputWalkability
from walkability.operator_worker import OperatorWalkability
from walkability.utils import filter_start_matcher


def pytest_addoption(parser):
    parser.addoption('--skip-slow', action='store_true', default=False, help='Skip slow tests')


def pytest_collection_modifyitems(config, items):
    if config.getoption('--skip-slow'):
        skipper = pytest.mark.skip(reason='Skip slow tests if --skip-slow is given')
        for item in items:
            if 'slow' in item.keywords:
                item.add_marker(skipper)


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
def operator(naturalness_utility_mock):
    return OperatorWalkability(naturalness_utility_mock)


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


@pytest.fixture
def naturalness_utility_mock():
    with patch('climatoology.utility.Naturalness.NaturalnessUtility') as naturalness_utility:
        vectors = gpd.GeoSeries(
            index=[1, 2],
            data=[
                Polygon([[7.381, 47.51], [7.385, 47.51], [7.385, 47.511], [7.381, 47.511], [7.381, 47.51]]),
                Polygon([[7.381, 47.51], [7.385, 47.51], [7.385, 47.511], [7.381, 47.511], [7.381, 47.51]]),
            ],
            crs=CRS.from_epsg(4326),
        )
        return_gdf = gpd.GeoDataFrame(
            index=[1, 2], data={'median': [0.5, 0.6]}, geometry=vectors, crs=CRS.from_epsg(4326)
        )

        naturalness_utility.compute_vector.return_value = return_gdf
        yield naturalness_utility
